from abc import ABC, abstractmethod
from typing import Optional


class InputSource(ABC):
    """Abstract input source. Keyboard now, STT later."""

    @property
    def ready_message(self) -> str:
        """Message spoken when the app is ready for input."""
        return "Claude Voice is starting."

    @abstractmethod
    async def get_prompt(self) -> Optional[str]:
        """Get the next user prompt. Returns None to quit."""
        ...
