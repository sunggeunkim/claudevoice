from rich.console import Console

from claudevoice.claude.messages import ClaudeMessage, MessageKind
from claudevoice.ui.components import (
    cost_footer,
    error_panel,
    session_banner,
    tool_panel,
)
from claudevoice.ui.markdown_stream import StreamingMarkdown


class VisualRenderer:
    """Renders Claude messages to the terminal with Rich formatting."""

    def __init__(self, console: Console, show_thinking: bool = False):
        self._console = console
        self._show_thinking = show_thinking
        self._markdown = StreamingMarkdown(console)

    def render(self, message: ClaudeMessage) -> None:
        # Finish streaming markdown before rendering non-text messages
        if self._markdown.is_active and message.kind != MessageKind.TEXT_CHUNK:
            self._markdown.finish()

        if message.kind == MessageKind.SESSION_INIT:
            if message.session_id:
                self._console.print(session_banner(message.session_id))

        elif message.kind == MessageKind.TEXT_CHUNK:
            if not self._markdown.is_active:
                self._markdown.start()
            self._markdown.feed(message.text)

        elif message.kind == MessageKind.TOOL_START:
            self._console.print(tool_panel(message))

        elif message.kind == MessageKind.ERROR:
            self._console.print(error_panel(message.text))

        elif message.kind == MessageKind.RESULT:
            footer = cost_footer(message)
            if footer is not None:
                self._console.print(footer)

        elif message.kind == MessageKind.THINKING:
            if self._show_thinking:
                self._console.print(message.text, style="thinking")

    def finalize(self) -> None:
        if self._markdown.is_active:
            self._markdown.finish()


class NullRenderer:
    """No-op renderer for pure TTS mode."""

    def render(self, message: ClaudeMessage) -> None:
        pass

    def finalize(self) -> None:
        pass
