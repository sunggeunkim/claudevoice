import asyncio
import signal
import sys

from claudevoice.claude.base import ClaudeBackend
from claudevoice.claude.messages import MessageKind
from claudevoice.pipeline.extractor import MessageExtractor
from claudevoice.pipeline.chunker import SentenceChunker
from claudevoice.tts.playback import PlaybackManager
from claudevoice.input.base import InputSource


class ClaudeVoiceApp:
    """Main application: prompt -> Claude -> extract -> speak."""

    def __init__(
        self,
        backend: ClaudeBackend,
        playback: PlaybackManager,
        input_source: InputSource,
        extractor: MessageExtractor | None = None,
    ):
        self._backend = backend
        self._playback = playback
        self._input = input_source
        self._extractor = extractor or MessageExtractor()
        self._running = True
        self._processing = False

    async def run(self) -> None:
        loop = asyncio.get_event_loop()
        if sys.platform != "win32":
            loop.add_signal_handler(signal.SIGINT, self._handle_interrupt)

        await self._playback.start()
        await self._playback.enqueue("Claude Voice is ready. Type your prompt.")
        await self._playback.drain()

        try:
            while self._running:
                prompt = await self._input.get_prompt()
                if prompt is None:
                    break
                await self._process_prompt(prompt)
        except KeyboardInterrupt:
            pass
        finally:
            await self._playback.enqueue("Goodbye.")
            await self._playback.drain()
            await self._playback.shutdown()
            await self._backend.close()

    async def _process_prompt(self, prompt: str) -> None:
        chunker = SentenceChunker()
        self._processing = True

        try:
            async for message in self._backend.send_prompt(prompt):
                text = self._extractor.extract(message)
                if text is None:
                    continue

                # Short messages (tool actions, results) — speak immediately
                if message.kind in (
                    MessageKind.TOOL_START,
                    MessageKind.RESULT,
                    MessageKind.ERROR,
                    MessageKind.SESSION_INIT,
                ):
                    await self._playback.enqueue(text)
                else:
                    # Text responses — chunk into sentences for streaming
                    sentences = chunker.feed(text)
                    for sentence in sentences:
                        await self._playback.enqueue(sentence)

            # Flush remaining text
            remaining = chunker.flush()
            if remaining:
                await self._playback.enqueue(remaining)

            await self._playback.drain()
        finally:
            self._processing = False

    def _handle_interrupt(self) -> None:
        if self._processing:
            asyncio.ensure_future(self._interrupt())
        else:
            self._running = False

    async def _interrupt(self) -> None:
        await self._playback.interrupt()
        await self._backend.interrupt()
        self._processing = False
        print("\n[Speech interrupted. Enter a new prompt.]")
