from typing import Optional

from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from claudevoice.claude.messages import ClaudeMessage


def tool_panel(message: ClaudeMessage) -> Panel:
    """Render a tool invocation as a cyan-bordered panel."""
    raw = message.raw or {}
    # For Bash tools, show the command in a syntax block
    if message.tool_name == "Bash":
        command = None
        msg_content = raw.get("message", {}).get("content", [])
        if isinstance(msg_content, list):
            for block in msg_content:
                if block.get("type") == "tool_use" and block.get("name") == "Bash":
                    command = block.get("input", {}).get("command")
                    break
        if command:
            body = Syntax(command, "bash", theme="monokai", word_wrap=True)
        else:
            body = Text(message.text)
    else:
        body = Text(message.text)

    return Panel(
        body,
        title=message.tool_name or "Tool",
        border_style="cyan",
        expand=False,
    )


def error_panel(text: str) -> Panel:
    """Render an error message as a red-bordered panel."""
    return Panel(
        Text(text, style="error"),
        title="Error",
        border_style="red",
        expand=False,
    )


def cost_footer(message: ClaudeMessage) -> Optional[Text]:
    """Render cost/duration info as a dim text line. Returns None if no data."""
    if message.cost_usd is None and message.duration_ms is None:
        return None

    parts = []
    if message.cost_usd is not None:
        parts.append(f"${message.cost_usd:.4f}")
    if message.duration_ms is not None:
        secs = message.duration_ms / 1000
        parts.append(f"{secs:.1f}s")
    if message.is_error:
        parts.append("(error)")

    return Text(" | ".join(parts), style="cost")


def session_banner(session_id: str) -> Text:
    """Render a dim session ID banner."""
    return Text(f"Session: {session_id}", style="banner")
