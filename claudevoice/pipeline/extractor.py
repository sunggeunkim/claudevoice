import re
from typing import Optional

from claudevoice.claude.messages import ClaudeMessage, MessageKind


def strip_markdown(text: str) -> str:
    """Strip markdown formatting for TTS-friendly plain text."""
    # Code blocks (``` ... ```) → keep content
    text = re.sub(r"```\w*\n?", "", text)
    # Inline code (`...`) → keep content
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Bold/italic (***text***, **text**, *text*)
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    # Underscores (__text__, _text_)
    text = re.sub(r"_{1,2}([^_]+)_{1,2}", r"\1", text)
    # Strikethrough (~~text~~)
    text = re.sub(r"~~([^~]+)~~", r"\1", text)
    # Headers (# ... ) → keep text
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Links [text](url) → just text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Images ![alt](url) → alt text
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    # Blockquotes
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    # Horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # List markers (-, *, numbered)
    text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[\s]*\d+\.\s+", "", text, flags=re.MULTILINE)
    return text


class MessageExtractor:
    """Extracts speakable text from ClaudeMessage objects."""

    def __init__(
        self, speak_tools: bool = True, speak_cost: bool = True, quiet: bool = False
    ):
        self.speak_tools = speak_tools
        self.speak_cost = speak_cost
        self.quiet = quiet

    def extract(self, message: ClaudeMessage) -> Optional[str]:
        """Return speakable text, or None to skip this message."""
        if message.kind == MessageKind.TEXT_CHUNK:
            text = strip_markdown(message.text)
            return text if text.strip() else None

        elif message.kind == MessageKind.TOOL_START:
            if self.quiet:
                return None
            if self.speak_tools:
                return message.text
            return None

        elif message.kind == MessageKind.ERROR:
            if self.quiet:
                return None
            return f"Error: {message.text}"

        elif message.kind == MessageKind.RESULT:
            if self.quiet:
                return None
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
            if self.quiet:
                return None
            return "Connected to Claude."

        elif message.kind == MessageKind.THINKING:
            return None

        return None
