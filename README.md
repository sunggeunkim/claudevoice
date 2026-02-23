# ClaudeVoice

An accessible interface to [Claude Code](https://claude.ai/claude-code) for blind and visually impaired users. ClaudeVoice reads Claude's responses aloud using natural-sounding text-to-speech, streaming sentences as they arrive so you hear output immediately.

## How it works

1. You type a prompt (speech-to-text input planned for the future)
2. ClaudeVoice sends it to the Claude Code CLI in the background
3. Claude's response is streamed back as structured JSON
4. Important content is extracted and spoken aloud sentence by sentence
5. Tool actions are announced ("Reading file auth.py", "Running command: git status")
6. When finished, cost and duration are announced

Press **Ctrl+C** at any time to interrupt speech and enter a new prompt.

## What gets spoken

- Claude's text responses, streamed sentence by sentence
- Tool action summaries (e.g. "Editing file main.py")
- Errors and warnings
- Task completion with cost and duration

Thinking blocks and raw tool output are skipped to keep things concise.

## Requirements

- Python 3.10+
- [Claude Code CLI](https://claude.ai/claude-code) installed and authenticated
- A Piper voice model (see setup below)
- Audio output (speakers or headphones)

## Setup

### Linux (Ubuntu/Debian)

Install system dependencies:

```bash
sudo apt-get install -y libportaudio2
```

Install ClaudeVoice:

```bash
cd claudevoice
uv venv && uv pip install -e .
```

Download a Piper voice model:

```bash
mkdir -p ~/.local/share/piper-voices
cd ~/.local/share/piper-voices
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
```

### macOS

Install PortAudio via Homebrew:

```bash
brew install portaudio
```

Install ClaudeVoice:

```bash
cd claudevoice
uv venv && uv pip install -e .
```

Download a Piper voice model:

```bash
mkdir -p ~/.local/share/piper-voices
cd ~/.local/share/piper-voices
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
```

### Windows

No extra system dependencies needed — `sounddevice` bundles PortAudio on Windows.

You may need [Visual C++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist) installed (required by `onnxruntime`).

Install ClaudeVoice:

```powershell
cd claudevoice
uv venv && uv pip install -e .
```

Download a Piper voice model into `%LOCALAPPDATA%\piper-voices\` or use `--tts-model` to point to any `.onnx` file:

```powershell
mkdir "$env:USERPROFILE\.local\share\piper-voices"
cd "$env:USERPROFILE\.local\share\piper-voices"
Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx" -OutFile "en_US-lessac-medium.onnx"
Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json" -OutFile "en_US-lessac-medium.onnx.json"
```

### WSL2 (Windows Subsystem for Linux)

Follow the Linux instructions above, plus set up audio routing to Windows:

```bash
sudo apt-get install -y libportaudio2 pulseaudio-utils
export PULSE_SERVER=unix:/mnt/wslg/PulseServer
```

Add the `export` line to your `~/.bashrc` to make it persistent. Requires Windows 11 with WSLg enabled (default on recent builds).

## Usage

Interactive mode (keeps prompting until you type `quit` or press Ctrl+C):

```bash
python -m claudevoice
```

One-shot mode (speaks the response and exits):

```bash
python -m claudevoice "explain what this project does"
```

### Options

```
--model MODEL        Claude model to use (e.g. sonnet, opus)
--tts-model PATH     Path to a Piper .onnx model file
--voice NAME         Piper voice name (default: en_US-lessac-medium)
--no-tools           Don't announce tool usage (quieter during heavy file operations)
--no-cost            Don't announce cost and duration at the end
```

### Examples

```bash
# Use a specific model
python -m claudevoice --model sonnet "fix the login bug"

# Quiet mode — only Claude's actual response, no tool announcements
python -m claudevoice --no-tools --no-cost "summarize this project"

# Use a custom voice model
python -m claudevoice --tts-model ~/voices/en_GB-alba-medium.onnx
```

## Running tests

```bash
uv pip install -e ".[dev]"
python -m pytest tests/ -v
```

## Architecture

```
User prompt
  → SubprocessBackend (claude -p --output-format stream-json)
  → ClaudeMessage (unified message type)
  → MessageExtractor (converts to speakable text)
  → SentenceChunker (splits into sentences for streaming)
  → PlaybackManager (async queue)
  → PiperTTSEngine (neural TTS → speakers)
```

The TTS engine and input source are abstracted behind base classes, making it straightforward to swap in a different TTS engine or add speech-to-text input in the future.
