import asyncio
from typing import Optional

from claudevoice.tts.base import TTSEngine


class PlaybackManager:
    """Manages a queue of text to speak, with interruption support."""

    def __init__(self, engine: TTSEngine):
        self._engine = engine
        self._queue: asyncio.Queue[Optional[str]] = asyncio.Queue(maxsize=100)
        self._task: Optional[asyncio.Task] = None
        self._interrupted = False

    async def start(self) -> None:
        await self._engine.initialize()
        self._task = asyncio.create_task(self._playback_loop())

    async def enqueue(self, text: str) -> None:
        if not self._interrupted:
            await self._queue.put(text)

    async def interrupt(self) -> None:
        self._interrupted = True
        await self._engine.stop()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self._interrupted = False

    async def drain(self) -> None:
        """Wait for all queued speech to finish."""
        await self._queue.put(None)
        if self._task:
            await self._task
        # Restart the playback loop for next prompt
        self._task = asyncio.create_task(self._playback_loop())

    async def _playback_loop(self) -> None:
        while True:
            text = await self._queue.get()
            if text is None:
                break
            if not self._interrupted:
                await self._engine.speak(text)

    async def shutdown(self) -> None:
        await self.interrupt()
        await self._queue.put(None)
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=2.0)
            except asyncio.TimeoutError:
                self._task.cancel()
        await self._engine.shutdown()


class NullPlaybackManager:
    """No-op playback manager for --no-tts mode."""

    async def start(self) -> None:
        pass

    async def enqueue(self, text: str) -> None:
        pass

    async def interrupt(self) -> None:
        pass

    async def drain(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass
