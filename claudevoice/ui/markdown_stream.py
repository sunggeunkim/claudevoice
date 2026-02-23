from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown


class StreamingMarkdown:
    """Accumulates text chunks and renders them as live-updating markdown."""

    def __init__(self, console: Console):
        self._console = console
        self._buffer = ""
        self._live: Live | None = None

    def start(self) -> None:
        self._buffer = ""
        self._live = Live(
            Markdown(""),
            console=self._console,
            refresh_per_second=10,
        )
        self._live.start()

    def feed(self, text: str) -> None:
        self._buffer += text
        if self._live is not None:
            self._live.update(Markdown(self._buffer))

    def finish(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None
        self._buffer = ""

    @property
    def is_active(self) -> bool:
        return self._live is not None
