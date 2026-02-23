import asyncio
import threading
from typing import Optional

from claudevoice.tts.base import TTSEngine


class PiperTTSEngine(TTSEngine):
    """Piper neural TTS engine with streaming audio playback."""

    def __init__(self, model_path: str):
        self._model_path = model_path
        self._voice = None
        self._lock = threading.Lock()
        self._stream = None
        self._speaking = False
        self._stop_event = threading.Event()

    async def initialize(self) -> None:
        from piper.voice import PiperVoice

        loop = asyncio.get_event_loop()
        self._voice = await loop.run_in_executor(
            None, PiperVoice.load, self._model_path
        )

    async def speak(self, text: str) -> None:
        if not text.strip():
            return

        self._stop_event.clear()
        self._speaking = True

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._speak_sync, text)
        finally:
            self._speaking = False

    def _speak_sync(self, text: str) -> None:
        """Synchronous speech synthesis and playback (runs in thread pool)."""
        import numpy as np
        import sounddevice as sd

        sample_rate = self._voice.config.sample_rate
        import platform

        is_wsl = "microsoft" in platform.release().lower()
        stream = sd.OutputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            latency="high" if is_wsl else None,
        )
        stream.start()
        with self._lock:
            self._stream = stream

        try:
            for chunk in self._voice.synthesize(text):
                if self._stop_event.is_set():
                    break
                stream.write(chunk.audio_int16_array)
        finally:
            stream.stop()
            stream.close()
            with self._lock:
                self._stream = None

    async def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            if self._stream is not None:
                try:
                    self._stream.abort()
                except Exception:
                    pass

    async def shutdown(self) -> None:
        await self.stop()
        self._voice = None

    @property
    def is_speaking(self) -> bool:
        return self._speaking
