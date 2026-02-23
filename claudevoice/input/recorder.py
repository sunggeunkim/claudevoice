"""Audio recording with Voice Activity Detection."""

import collections
import time
from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass
class RecordingResult:
    """Result of an audio recording session."""

    audio: np.ndarray  # float32, mono
    sample_rate: int
    duration_s: float


class VAD(Protocol):
    """Voice Activity Detection interface."""

    def is_speech(self, frame: np.ndarray) -> float:
        """Return speech probability (0.0–1.0) for a 16kHz float32 frame."""
        ...


class AmplitudeVAD:
    """Simple RMS-based VAD fallback when torch is unavailable."""

    def __init__(self, noise_floor: float = 0.01):
        self.noise_floor = noise_floor

    def is_speech(self, frame: np.ndarray) -> float:
        rms = float(np.sqrt(np.mean(frame**2)))
        if rms < self.noise_floor:
            return 0.0
        # Scale: noise_floor → 0.0, 3× noise_floor → 1.0
        ratio = (rms - self.noise_floor) / (self.noise_floor * 2)
        return float(np.clip(ratio, 0.0, 1.0))


class SileroVAD:
    """Silero VAD model wrapper."""

    def __init__(self):
        import torch

        model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            trust_repo=True,
        )
        self._model = model
        self._torch = torch

    def is_speech(self, frame: np.ndarray) -> float:
        tensor = self._torch.from_numpy(frame)
        prob = self._model(tensor, 16000)
        return float(prob.item())


def create_vad(noise_floor: float = 0.01) -> VAD:
    """Try Silero first, fall back to AmplitudeVAD."""
    try:
        return SileroVAD()
    except Exception:
        return AmplitudeVAD(noise_floor=noise_floor)


# Constants
FRAME_MS = 30
SAMPLE_RATE = 16000
FRAME_SIZE = int(SAMPLE_RATE * FRAME_MS / 1000)  # 480 samples
PRE_BUFFER_FRAMES = 11  # ~330ms to capture speech onset
START_THRESHOLD = 0.85
CONTINUE_THRESHOLD = 0.5
SILENCE_TIMEOUT_S = 2.0


class AudioRecorder:
    """Records speech from microphone with VAD-based endpoint detection."""

    def __init__(self, vad: VAD | None = None):
        self._vad = vad
        self._device_rate: int | None = None

    def _ensure_vad(self) -> VAD:
        if self._vad is None:
            self._vad = create_vad()
        return self._vad

    @staticmethod
    def _resample(audio: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
        """Resample audio using linear interpolation."""
        if from_rate == to_rate:
            return audio
        duration = len(audio) / from_rate
        new_length = int(duration * to_rate)
        old_indices = np.linspace(0, len(audio) - 1, new_length)
        orig_indices = np.arange(len(audio))
        return np.interp(old_indices, orig_indices, audio).astype(np.float32)

    def record(self) -> RecordingResult:
        """Record until speech ends. Blocks the calling thread."""
        import sounddevice as sd

        vad = self._ensure_vad()

        # Query default device sample rate
        device_info = sd.query_devices(kind="input")
        device_rate = int(device_info["default_samplerate"])
        device_frame_size = int(device_rate * FRAME_MS / 1000)

        # Ring buffer for incoming audio frames
        frame_buffer: collections.deque[np.ndarray] = collections.deque(maxsize=2000)
        # Pre-buffer to capture speech onset
        pre_buffer: collections.deque[np.ndarray] = collections.deque(
            maxlen=PRE_BUFFER_FRAMES
        )

        def callback(indata, frames, time_info, status):
            frame_buffer.append(indata[:, 0].copy())

        stream = sd.InputStream(
            samplerate=device_rate,
            channels=1,
            dtype="float32",
            blocksize=device_frame_size,
            callback=callback,
        )

        recorded_frames: list[np.ndarray] = []
        speech_started = False
        last_speech_time = 0.0

        with stream:
            while True:
                if not frame_buffer:
                    time.sleep(0.005)
                    continue

                raw_frame = frame_buffer.popleft()

                # Resample to 16kHz for VAD
                frame_16k = self._resample(raw_frame, device_rate, SAMPLE_RATE)
                prob = vad.is_speech(frame_16k)

                if not speech_started:
                    pre_buffer.append(raw_frame)
                    if prob >= START_THRESHOLD:
                        speech_started = True
                        last_speech_time = time.monotonic()
                        # Include pre-buffer
                        recorded_frames.extend(pre_buffer)
                        pre_buffer.clear()
                else:
                    recorded_frames.append(raw_frame)
                    if prob >= CONTINUE_THRESHOLD:
                        last_speech_time = time.monotonic()
                    elif time.monotonic() - last_speech_time > SILENCE_TIMEOUT_S:
                        break

        if not recorded_frames:
            return RecordingResult(
                audio=np.array([], dtype=np.float32),
                sample_rate=SAMPLE_RATE,
                duration_s=0.0,
            )

        audio = np.concatenate(recorded_frames)
        # Resample to 16kHz for Whisper
        audio_16k = self._resample(audio, device_rate, SAMPLE_RATE)
        duration = len(audio_16k) / SAMPLE_RATE

        return RecordingResult(
            audio=audio_16k, sample_rate=SAMPLE_RATE, duration_s=duration
        )
