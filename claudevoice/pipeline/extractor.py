from typing import Optional

from claudevoice.claude.messages import ClaudeMessage, MessageKind


class MessageExtractor:
    """Extracts speakable text from ClaudeMessage objects."""

    def __init__(self, speak_tools: bool = True, speak_cost: bool = True):
        self.speak_tools = speak_tools
        self.speak_cost = speak_cost

    def extract(self, message: ClaudeMessage) -> Optional[str]:
        """Return speakable text, or None to skip this message."""
        if message.kind == MessageKind.TEXT_CHUNK:
            return message.text if message.text.strip() else None

        elif message.kind == MessageKind.TOOL_START:
            if self.speak_tools:
                return message.text
            return None

        elif message.kind == MessageKind.ERROR:
            return f"Error: {message.text}"

        elif message.kind == MessageKind.RESULT:
            parts = []
            if message.is_error:
                parts.append(f"Task failed: {message.text}")
            else:
                parts.append("Task complete.")
            if self.speak_cost and message.cost_usd is not None:
                parts.append(f"Cost: {message.cost_usd:.4f} dollars.")
            if message.duration_ms is not None:
                secs = message.duration_ms / 1000
                parts.append(f"Duration: {secs:.1f} seconds.")
            return " ".join(parts)

        elif message.kind == MessageKind.SESSION_INIT:
            return "Connected to Claude."

        elif message.kind == MessageKind.THINKING:
            return None

        return None
