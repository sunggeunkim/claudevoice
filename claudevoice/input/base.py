from abc import ABC, abstractmethod
from typing import Optional


class InputSource(ABC):
    """Abstract input source. Keyboard now, STT later."""

    @abstractmethod
    async def get_prompt(self) -> Optional[str]:
        """Get the next user prompt. Returns None to quit."""
        ...
