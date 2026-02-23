from dataclasses import dataclass
from typing import Optional


@dataclass
class ClaudeVoiceConfig:
    # Claude settings
    claude_model: Optional[str] = None
    claude_path: str = "claude"

    # TTS settings
    tts_engine: str = "piper"
    piper_model: Optional[str] = None
    piper_voice: str = "en_US-lessac-medium"

    # Speech behavior
    speak_tools: bool = True
    speak_cost: bool = True
