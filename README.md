# ClaudeVoice

An accessible interface to [Claude Code](https://claude.ai/claude-code) for blind and visually impaired users. ClaudeVoice displays Claude's responses with rich terminal formatting — markdown rendering, syntax-highlighted code, colored tool panels — while simultaneously reading them aloud via text-to-speech. Conversations persist across prompts with multi-turn support.

## How it works

1. You type a prompt (or use speech-to-text with `--voice-input`)
2. ClaudeVoice sends it to the Claude Code CLI in the background
3. Claude's response is streamed back as structured JSON
4. Responses are **displayed** in the terminal with Rich markdown rendering and **spoken** via TTS simultaneously
5. Tool actions appear as colored panels and are announced aloud
6. When finished, cost and duration are shown and spoken
7. Follow-up prompts continue the same conversation automatically

Press **Ctrl+C** at any time to interrupt speech and enter a new prompt.

## What you see and hear

- Claude's text responses rendered as markdown with syntax-highlighted code blocks
- Tool invocations shown as cyan-bordered panels (with command syntax for Bash tools)
- Errors highlighted in red panels
- Cost and duration displayed after each response
- All of the above spoken aloud via TTS (unless `--no-tts` is used)

Thinking blocks are hidden by default (enable with `--show-thinking`).

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
curl -L -o ~/.local/share/piper-voices/en_US-lessac-medium.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
curl -L -o ~/.local/share/piper-voices/en_US-lessac-medium.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
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
curl -L -o ~/.local/share/piper-voices/en_US-lessac-medium.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
curl -L -o ~/.local/share/piper-voices/en_US-lessac-medium.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
```

### Windows

No extra system dependencies needed — `sounddevice` bundles PortAudio on Windows.

You may need [Visual C++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist) installed (required by `onnxruntime`).

Install ClaudeVoice:

```powershell
cd claudevoice
uv venv && uv pip install -e .
```

Download a Piper voice model (or use `--tts-model` to point to any `.onnx` file):

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.local\share\piper-voices"
Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx" -OutFile "$env:USERPROFILE\.local\share\piper-voices\en_US-lessac-medium.onnx"
Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json" -OutFile "$env:USERPROFILE\.local\share\piper-voices\en_US-lessac-medium.onnx.json"
```

### WSL2 (Windows Subsystem for Linux)

Follow the Linux instructions above, plus set up audio routing to Windows:

```bash
sudo apt-get install -y libportaudio2 pulseaudio-utils
export PULSE_SERVER=unix:/mnt/wslg/PulseServer
```

Add the `export` line to your `~/.bashrc` to make it persistent. Requires Windows 11 with WSLg enabled (default on recent builds).

## Usage

### Option A: Add to PATH (run from anywhere)

This lets you run `claudevoice` from any directory without activating the venv.

**Linux / macOS / WSL2** — add to `~/.bashrc` (or `~/.zshrc`):

```bash
echo 'alias claudevoice="~/claudevoice/.venv/bin/claudevoice"' >> ~/.bashrc
source ~/.bashrc
```

**Windows (PowerShell)** — add to your PowerShell profile:

```powershell
Add-Content $PROFILE 'function claudevoice { & "$env:USERPROFILE\repos\claudevoice\.venv\Scripts\claudevoice.exe" @args }'
. $PROFILE
```

> Adjust the path if your repo is in a different location.

### Option B: Activate the virtual environment

Activate the venv each time before running:

**Linux / macOS / WSL2:**

```bash
cd claudevoice
source .venv/bin/activate
```

**Windows (PowerShell):**

```powershell
cd claudevoice
.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**

```cmd
cd claudevoice
.venv\Scripts\activate.bat
```

### Option C: Use `uv run`

Skip activation entirely:

```bash
cd claudevoice
uv run python -m claudevoice
```

### Running ClaudeVoice

If you set up Option A above, you can run `claudevoice` directly from anywhere:

```bash
claudevoice
```

Otherwise, use `python -m claudevoice` with the venv activated or `uv run`.

Interactive mode (keeps prompting until you type `quit` or press Ctrl+C):

```bash
claudevoice
```

One-shot mode (speaks the response and exits):

```bash
claudevoice "explain what this project does"
```

Visual-only mode (no TTS, just rich terminal output):

```bash
claudevoice --no-tts
```

### Options

```
--model MODEL          Claude model to use (e.g. sonnet, opus)
--tts-model PATH       Path to a Piper .onnx model file
--voice NAME           Piper voice name (default: en_US-lessac-medium)
--no-tools             Don't announce tool usage (quieter during heavy file operations)
--no-cost              Don't announce cost and duration at the end
--no-tts               Disable TTS entirely, visual output only
--continue, -c         Resume the most recent conversation
--resume, -r ID        Resume a specific conversation by session ID
--show-thinking        Display thinking blocks in dim style
--voice-input          Use speech-to-text input instead of keyboard
--whisper-model SIZE   Whisper model size for voice input (default: base)
--wake-word            Require 'Hey Claude' wake phrase (use with --voice-input)
```

### Examples

```bash
# Use a specific model
python -m claudevoice --model sonnet "fix the login bug"

# Visual only — no TTS, just rich terminal rendering
python -m claudevoice --no-tts "summarize this project"

# Quiet mode — no tool announcements or cost readout
python -m claudevoice --no-tools --no-cost "summarize this project"

# Continue the most recent conversation
python -m claudevoice -c

# Resume a specific session
python -m claudevoice -r abc123-session-id

# Use a custom voice model
python -m claudevoice --tts-model ~/voices/en_GB-alba-medium.onnx

# Voice input with wake word
python -m claudevoice --voice-input --wake-word
```

## Voice input (optional)

To use speech-to-text input (`--voice-input`), install the extra dependencies:

```bash
uv pip install -e ".[voice]"
```

This installs OpenAI Whisper and PyTorch. Then run:

```bash
python -m claudevoice --voice-input -q --permission-mode acceptEdits
```

`-q` suppresses status announcements so you only hear Claude's response. `--permission-mode acceptEdits` auto-approves file operations so Claude doesn't hang waiting for keyboard approval.

### How voice input works

1. You'll hear **"Claude Voice is starting."** — wait, don't speak yet.
2. On first run, it calibrates your microphone noise level (2 seconds of silence).
3. **After the startup sound finishes, start speaking.** There is no "listening" prompt — it silently begins recording.
4. Speak your prompt naturally. The recorder detects when you stop talking (2 seconds of silence).
5. You'll hear **"Processing."** while Whisper transcribes your speech.
6. You'll hear **"You said: ..."** confirming what was transcribed, then Claude's response.
7. After the response finishes, it silently starts listening again — just speak your next prompt.

### Wake word mode

Add `--wake-word` to require saying "Hey Claude" before each prompt:

```bash
python -m claudevoice --voice-input --wake-word -q --permission-mode acceptEdits
```

In this mode, the microphone is always listening but ignores everything until it hears "Hey Claude". You can either say "Hey Claude, explain this repo" in one breath, or say "Hey Claude" alone and wait for "Yes?" before speaking your prompt.

## Running tests

```bash
uv pip install -e ".[dev]"
python -m pytest tests/ -v
```

## Architecture

```
User prompt
  → SubprocessBackend (claude -p --output-format stream-json --resume)
  → ClaudeMessage (unified message type)
  ├→ VisualRenderer (Rich markdown, tool panels, cost footer → terminal)
  └→ MessageExtractor (converts to speakable text)
     → SentenceChunker (splits into sentences for streaming)
     → PlaybackManager (async queue)
     → PiperTTSEngine (neural TTS → speakers)
```

The TTS engine, input source, and renderer are abstracted behind base classes. Use `NullPlaybackManager` for visual-only mode or `NullRenderer` for TTS-only mode.
