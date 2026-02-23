from abc import ABC, abstractmethod
from typing import AsyncIterator

from claudevoice.claude.messages import ClaudeMessage


class ClaudeBackend(ABC):
    """Abstract interface for communicating with Claude Code."""

    @abstractmethod
    async def send_prompt(
        self, prompt: str, *, session_id: str | None = None
    ) -> AsyncIterator[ClaudeMessage]:
        ...

    @abstractmethod
    async def interrupt(self) -> None:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...
