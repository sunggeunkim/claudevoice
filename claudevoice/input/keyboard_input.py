import asyncio
from typing import Optional

from claudevoice.input.base import InputSource


class KeyboardInput(InputSource):
    """Keyboard/stdin input source."""

    @property
    def ready_message(self) -> str:
        return "Claude Voice is ready. Type your prompt."

    async def get_prompt(self) -> Optional[str]:
        loop = asyncio.get_event_loop()
        while True:
            try:
                line = await loop.run_in_executor(
                    None, lambda: input("\nYou: ")
                )
                line = line.strip()
                if line.lower() in ("quit", "exit", "q"):
                    return None
                if line:
                    return line
            except (EOFError, KeyboardInterrupt):
                return None
