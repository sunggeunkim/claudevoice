# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ClaudeVoice is an accessible interface to Claude Code for blind and visually impaired users. It provides simultaneous rich terminal rendering and text-to-speech output, with optional voice input via Whisper.

## Build and Run

```bash
# Install (basic)
uv venv && uv pip install -e .

# Install with voice input (Whisper + PyTorch)
uv pip install -e ".[voice]"

# Install dev dependencies
uv pip install -e ".[dev]"

# System dependency: libportaudio2 (Linux), portaudio (macOS)

# Run interactively
claudevoice

# One-shot prompt
claudevoice "explain this code"
```

## Tests

```bash
pytest tests/ -v
pytest tests/test_chunker.py::test_single_sentence -v   # single test
```

Tests use `pytest` and `pytest-asyncio`. No lint/format tooling is currently configured.

## Architecture

**Data flow:** User input → `SubprocessBackend` spawns `claude` CLI with `--output-format stream-json` → NDJSON lines parsed into `ClaudeMessage` objects → streamed concurrently to `VisualRenderer` (Rich terminal) and TTS pipeline (`MessageExtractor` → `SentenceChunker` → `PlaybackManager` → `PiperTTSEngine`).

### Key modules

- **`claudevoice/app.py`** — `ClaudeVoiceApp`: main event loop, interrupt handling, coordinates all subsystems
- **`claudevoice/claude/`** — `ClaudeBackend` abstract interface; `SubprocessBackend` spawns claude CLI and parses NDJSON stream into `ClaudeMessage` (unified type with kinds: TEXT_CHUNK, TOOL_START, TOOL_RESULT, ERROR, RESULT, SESSION_INIT, THINKING)
- **`claudevoice/pipeline/`** — `MessageExtractor` strips markdown for TTS; `SentenceChunker` splits at sentence boundaries for streaming speech (min 20 chars, max 500, force-breaks at word boundary)
- **`claudevoice/tts/`** — `TTSEngine` abstract interface; `PiperTTSEngine` does ONNX neural synthesis; `PlaybackManager` manages async queue with interruption support
- **`claudevoice/ui/`** — `VisualRenderer` renders Rich markdown/panels; `StreamingMarkdown` for live text; `RichInput` for keyboard input
- **`claudevoice/input/`** — `InputSource` abstract interface; `VoiceInput` uses Whisper with optional wake word detection

### Null object pattern

`NullPlaybackManager` and `NullRenderer` are used when `--no-tts` or TTS-only modes are active, avoiding conditional checks throughout the codebase.

### TTS system prompt

When TTS is active, a system prompt is appended asking Claude to format output for listening: plain text instead of tables, repeat column names with values, short conversational sentences, no raw URLs.

### Session management

Claude responses include `session_id` stored in `SubprocessBackend._last_session_id`. The `--continue` flag resumes the last session; `--resume SESSION_ID` resumes a specific one.

### Interrupt handling (Ctrl+C)

Signal handler in `app.py` cancels playback, interrupts the Claude subprocess, and cancels prompt/loop tasks. Recent fixes addressed deadlocks from incomplete task cancellation.

## Entry point

`claudevoice/__main__.py` — argparse CLI with flags for model selection, TTS model path, voice input, quiet mode, session resume, and permission modes.
