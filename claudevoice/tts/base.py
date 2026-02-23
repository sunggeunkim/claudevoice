from abc import ABC, abstractmethod


class TTSEngine(ABC):
    """Abstract base class for text-to-speech engines."""

    @abstractmethod
    async def initialize(self) -> None:
        ...

    @abstractmethod
    async def speak(self, text: str) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        ...

    @property
    @abstractmethod
    def is_speaking(self) -> bool:
        ...
