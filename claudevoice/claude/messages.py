from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MessageKind(Enum):
    SESSION_INIT = "session_init"
    TEXT_CHUNK = "text_chunk"
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    RESULT = "result"
    THINKING = "thinking"


@dataclass
class ClaudeMessage:
    kind: MessageKind
    text: str = ""
    tool_name: Optional[str] = None
    tool_input_summary: Optional[str] = None
    is_error: bool = False
    cost_usd: Optional[float] = None
    duration_ms: Optional[int] = None
    session_id: Optional[str] = None
    raw: Optional[dict] = field(default=None, repr=False)
