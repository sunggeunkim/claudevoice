"""Tests for voice input components — no audio hardware needed."""

import asyncio
import re
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from claudevoice.input.recorder import AmplitudeVAD, AudioRecorder, RecordingResult
from claudevoice.input.wake_word import WakeWordDetector
from claudevoice.input.transcriber import EMPTY_RESULTS


# ── AmplitudeVAD ──


def test_amplitude_vad_silence():
    vad = AmplitudeVAD(noise_floor=0.01)
    silence = np.zeros(480, dtype=np.float32)
    assert vad.is_speech(silence) == 0.0


def test_amplitude_vad_loud_signal():
    vad = AmplitudeVAD(noise_floor=0.01)
    loud = np.full(480, 0.5, dtype=np.float32)
    prob = vad.is_speech(loud)
    assert prob == 1.0


def test_amplitude_vad_moderate_signal():
    vad = AmplitudeVAD(noise_floor=0.01)
    moderate = np.full(480, 0.02, dtype=np.float32)
    prob = vad.is_speech(moderate)
    assert 0.0 < prob < 1.0


# ── WakeWordDetector ──


def test_wake_word_exact_match():
    d = WakeWordDetector()
    assert d.matches_wake_phrase("hey claude") is True


def test_wake_word_case_insensitive():
    d = WakeWordDetector()
    assert d.matches_wake_phrase("Hey Claude") is True
    assert d.matches_wake_phrase("HEY CLAUDE") is True


def test_wake_word_variant():
    d = WakeWordDetector()
    assert d.matches_wake_phrase("hey cloud") is True
    assert d.matches_wake_phrase("hey clod") is True


def test_wake_word_fuzzy():
    d = WakeWordDetector()
    assert d.matches_wake_phrase("hey claud") is True


def test_wake_word_prefix():
    d = WakeWordDetector()
    assert d.matches_wake_phrase("hey claude, what time is it") is True


def test_wake_word_no_match():
    d = WakeWordDetector()
    assert d.matches_wake_phrase("hello world") is False
    assert d.matches_wake_phrase("okay google") is False


def test_wake_word_empty():
    d = WakeWordDetector()
    assert d.matches_wake_phrase("") is False
    assert d.matches_wake_phrase("   ") is False


def test_wake_word_punctuation_only():
    d = WakeWordDetector()
    assert d.matches_wake_phrase("...") is False


def test_extract_command():
    d = WakeWordDetector()
    assert d.extract_command("hey claude, what is python") == "what is python"
    assert d.extract_command("hey claude") is None
    assert d.extract_command("hey cloud, tell me a joke") == "tell me a joke"


# ── EMPTY_RESULTS regex ──


def test_empty_results_filters_punctuation():
    assert EMPTY_RESULTS.match("...") is not None
    assert EMPTY_RESULTS.match("  ") is not None
    assert EMPTY_RESULTS.match(",,,") is not None
    assert EMPTY_RESULTS.match("!?") is not None


def test_empty_results_filters_hallucinations():
    assert EMPTY_RESULTS.match("you") is not None
    assert EMPTY_RESULTS.match("You.") is not None
    assert EMPTY_RESULTS.match("thank you") is not None
    assert EMPTY_RESULTS.match("Thanks") is not None


def test_empty_results_passes_real_text():
    assert EMPTY_RESULTS.match("what is the weather") is None
    assert EMPTY_RESULTS.match("hey claude") is None
    assert EMPTY_RESULTS.match("explain python") is None


# ── AudioRecorder._resample ──


def test_resample_same_rate():
    audio = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32)
    result = AudioRecorder._resample(audio, 16000, 16000)
    np.testing.assert_array_equal(result, audio)


def test_resample_downsample():
    audio = np.ones(48000, dtype=np.float32)  # 1s at 48kHz
    result = AudioRecorder._resample(audio, 48000, 16000)
    assert len(result) == 16000
    assert result.dtype == np.float32


def test_resample_upsample():
    audio = np.ones(16000, dtype=np.float32)  # 1s at 16kHz
    result = AudioRecorder._resample(audio, 16000, 48000)
    assert len(result) == 48000
    assert result.dtype == np.float32


# ── VoiceInput.get_prompt (mocked) ──


@pytest.mark.asyncio
async def test_voice_input_get_prompt_direct():
    """Direct mode: record → transcribe → return text."""
    from claudevoice.input.voice_input import VoiceInput

    vi = VoiceInput(wake_word=False, playback=None)

    fake_result = RecordingResult(
        audio=np.zeros(16000, dtype=np.float32),
        sample_rate=16000,
        duration_s=1.0,
    )
    mock_recorder = MagicMock()
    mock_recorder.record.return_value = fake_result

    mock_transcriber = MagicMock()
    mock_transcriber.transcribe = AsyncMock(return_value="hello world")

    vi._recorder = mock_recorder
    vi._transcriber = mock_transcriber
    vi._calibrated = True

    prompt = await vi.get_prompt()
    assert prompt == "hello world"


@pytest.mark.asyncio
async def test_voice_input_retries_on_empty():
    """Direct mode retries when transcription returns None, then succeeds."""
    from claudevoice.input.voice_input import VoiceInput

    vi = VoiceInput(wake_word=False, playback=None)

    fake_result = RecordingResult(
        audio=np.zeros(16000, dtype=np.float32),
        sample_rate=16000,
        duration_s=1.0,
    )
    mock_recorder = MagicMock()
    mock_recorder.record.return_value = fake_result

    mock_transcriber = MagicMock()
    # First call returns None, second returns text
    mock_transcriber.transcribe = AsyncMock(side_effect=[None, "try again"])

    vi._recorder = mock_recorder
    vi._transcriber = mock_transcriber
    vi._calibrated = True

    prompt = await vi.get_prompt()
    assert prompt == "try again"
    assert mock_transcriber.transcribe.call_count == 2
