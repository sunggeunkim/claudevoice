"""Whisper-based speech-to-text transcription."""

import asyncio
import re
from typing import Optional

import numpy as np

# Matches empty/hallucinated Whisper outputs
EMPTY_RESULTS = re.compile(
    r"^[\s.,!?\-—…]*$"  # punctuation/whitespace only
    r"|^(you|thank you|thanks)\.?$",  # common hallucinations
    re.IGNORECASE,
)


class Transcriber:
    """Wraps OpenAI Whisper for speech-to-text."""

    def __init__(self, model_name: str = "base"):
        self._model_name = model_name
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            import whisper

            self._model = whisper.load_model(self._model_name)

    def transcribe_sync(self, audio: np.ndarray) -> Optional[str]:
        """Transcribe audio (16kHz float32). Returns None for empty results."""
        self._ensure_model()
        result = self._model.transcribe(
            audio, language="en", fp16=False, no_speech_threshold=0.6
        )
        text = result["text"].strip()
        if not text or EMPTY_RESULTS.match(text):
            return None
        return text

    async def transcribe(self, audio: np.ndarray) -> Optional[str]:
        """Async wrapper — runs transcription in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.transcribe_sync, audio)


class QuickTranscriber:
    """Uses Whisper 'tiny' model for fast wake word detection."""

    def __init__(self):
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            import whisper

            self._model = whisper.load_model("tiny")

    def transcribe_sync(self, audio: np.ndarray) -> Optional[str]:
        """Fast transcription for wake word detection."""
        self._ensure_model()
        result = self._model.transcribe(
            audio, language="en", fp16=False, no_speech_threshold=0.6
        )
        text = result["text"].strip()
        if not text or EMPTY_RESULTS.match(text):
            return None
        return text

    async def transcribe(self, audio: np.ndarray) -> Optional[str]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.transcribe_sync, audio)
