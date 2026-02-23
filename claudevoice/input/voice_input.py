"""Voice input source using Whisper STT with VAD."""

import asyncio
import json
import os
from typing import Optional, TYPE_CHECKING

from claudevoice.input.base import InputSource

if TYPE_CHECKING:
    from claudevoice.tts.playback import PlaybackManager


class VoiceInput(InputSource):
    """Speech-to-text input source using Whisper and VAD."""

    def __init__(
        self,
        whisper_model: str = "base",
        wake_word: bool = False,
        playback: Optional["PlaybackManager"] = None,
    ):
        self._whisper_model = whisper_model
        self._wake_word = wake_word
        self._playback = playback

        # Lazy-initialized components
        self._recorder = None
        self._transcriber = None
        self._quick_transcriber = None
        self._wake_detector = None
        self._calibrated = False

    @property
    def ready_message(self) -> str:
        if self._wake_word:
            return "Claude Voice is ready. Say 'Hey Claude' to begin."
        return "Claude Voice is ready. Start speaking."

    def _ensure_components(self):
        """Lazy-init all heavy components."""
        if self._recorder is not None:
            return

        from claudevoice.input.recorder import AudioRecorder, create_vad
        from claudevoice.input.transcriber import Transcriber

        vad = create_vad()
        self._recorder = AudioRecorder(vad=vad)
        self._transcriber = Transcriber(model_name=self._whisper_model)

        if self._wake_word:
            from claudevoice.input.transcriber import QuickTranscriber
            from claudevoice.input.wake_word import WakeWordDetector

            self._quick_transcriber = QuickTranscriber()
            self._wake_detector = WakeWordDetector()

    async def _calibrate_noise(self):
        """Record 2s of silence to calibrate noise floor."""
        if self._calibrated:
            return

        cal_path = os.path.expanduser("~/.claude/noise_calibration.json")
        if os.path.exists(cal_path):
            try:
                with open(cal_path) as f:
                    data = json.load(f)
                from claudevoice.input.recorder import AmplitudeVAD

                if isinstance(self._recorder._vad, AmplitudeVAD):
                    self._recorder._vad.noise_floor = data.get(
                        "noise_floor", 0.01
                    )
                self._calibrated = True
                return
            except Exception:
                pass

        if self._playback:
            await self._playback.enqueue("Calibrating noise level. Please stay quiet.")
            await self._playback.drain()

        import numpy as np
        import sounddevice as sd

        device_info = sd.query_devices(kind="input")
        device_rate = int(device_info["default_samplerate"])
        duration = 2.0
        loop = asyncio.get_event_loop()
        audio = await loop.run_in_executor(
            None,
            lambda: sd.rec(
                int(duration * device_rate),
                samplerate=device_rate,
                channels=1,
                dtype="float32",
            ),
        )
        await loop.run_in_executor(None, sd.wait)

        rms = float(np.sqrt(np.mean(audio**2)))
        noise_floor = rms * 2.0  # Set threshold above ambient noise

        os.makedirs(os.path.dirname(cal_path), exist_ok=True)
        with open(cal_path, "w") as f:
            json.dump({"noise_floor": noise_floor}, f)

        from claudevoice.input.recorder import AmplitudeVAD

        if isinstance(self._recorder._vad, AmplitudeVAD):
            self._recorder._vad.noise_floor = noise_floor

        self._calibrated = True

    async def _speak(self, text: str):
        """Speak feedback if playback is available."""
        if self._playback:
            await self._playback.enqueue(text)
            await self._playback.drain()

    async def _record_and_transcribe(self) -> Optional[str]:
        """Record speech and transcribe it."""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._recorder.record)

        if result.duration_s < 0.3:
            return None

        await self._speak("Processing.")
        text = await self._transcriber.transcribe(result.audio)
        return text

    async def get_prompt(self) -> Optional[str]:
        try:
            self._ensure_components()
        except Exception:
            return None

        await self._calibrate_noise()

        if self._wake_word:
            return await self._get_prompt_wake()
        return await self._get_prompt_direct()

    async def _get_prompt_direct(self) -> Optional[str]:
        """Direct listen mode: announce → record → transcribe → return."""
        while True:
            await self._speak("Listening.")
            text = await self._record_and_transcribe()
            if text is None:
                await self._speak("I didn't catch that. Try again.")
                continue

            await self._speak(f"You said: {text}")
            return text

    async def _get_prompt_wake(self) -> Optional[str]:
        """Wake word mode: listen for 'hey claude', then capture command."""
        while True:
            # Listen for wake phrase with quick transcriber
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._recorder.record)

            if result.duration_s < 0.3:
                continue

            text = await self._quick_transcriber.transcribe(result.audio)
            if text is None:
                continue

            if not self._wake_detector.matches_wake_phrase(text):
                continue

            # Check if command was included with wake phrase
            command = self._wake_detector.extract_command(text)
            if command:
                await self._speak(f"You said: {command}")
                return command

            # No command — enter direct listen for one prompt
            await self._speak("Yes?")
            return await self._get_prompt_direct()
