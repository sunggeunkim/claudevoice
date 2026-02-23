import asyncio
from typing import Optional

from rich.console import Console

from claudevoice.input.base import InputSource


class RichInput(InputSource):
    """Rich-styled terminal input source."""

    def __init__(self, console: Console):
        self._console = console

    @property
    def ready_message(self) -> str:
        return "Claude Voice is ready."

    async def get_prompt(self) -> Optional[str]:
        loop = asyncio.get_event_loop()
        while True:
            try:
                line = await loop.run_in_executor(
                    None, lambda: self._console.input("[bold blue]You:[/] ")
                )
                line = line.strip()
                if line.lower() in ("quit", "exit", "q"):
                    return None
                if line:
                    return line
            except (EOFError, KeyboardInterrupt):
                return None
