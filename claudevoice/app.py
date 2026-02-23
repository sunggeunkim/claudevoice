import asyncio
import signal
import sys

from claudevoice.claude.base import ClaudeBackend
from claudevoice.claude.messages import MessageKind
from claudevoice.pipeline.extractor import MessageExtractor
from claudevoice.pipeline.chunker import SentenceChunker
from claudevoice.input.base import InputSource
from claudevoice.ui.renderer import NullRenderer


class ClaudeVoiceApp:
    """Main application: prompt -> Claude -> extract -> speak + render."""

    def __init__(
        self,
        backend: ClaudeBackend,
        playback,
        input_source: InputSource,
        extractor: MessageExtractor | None = None,
        renderer=None,
    ):
        self._backend = backend
        self._playback = playback
        self._input = input_source
        self._extractor = extractor or MessageExtractor()
        self._renderer = renderer or NullRenderer()
        self._running = True
        self._processing = False
        self._interrupted = False
        self._first_prompt = True

    async def run(self) -> None:
        loop = asyncio.get_event_loop()
        if sys.platform == "win32":
            signal.signal(signal.SIGINT, lambda *_: self._handle_interrupt())
        else:
            loop.add_signal_handler(signal.SIGINT, self._handle_interrupt)

        await self._playback.start()
        await self._playback.enqueue(self._input.ready_message)
        await self._playback.drain()

        try:
            while self._running:
                prompt = await self._input.get_prompt()
                if prompt is None:
                    break
                try:
                    await self._process_prompt(prompt)
                except asyncio.CancelledError:
                    pass
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
        self._interrupted = False
        quiet = self._extractor.quiet

        if quiet:
            await self._playback.enqueue(
                "Processing your request. This may take a moment."
            )

        try:
            sid = None
            if not self._first_prompt:
                sid = getattr(self._backend, "last_session_id", None)

            async for message in self._backend.send_prompt(
                prompt, session_id=sid
            ):
                self._renderer.render(message)

                if quiet and message.kind in (
                    MessageKind.TOOL_START,
                    MessageKind.RESULT,
                    MessageKind.ERROR,
                    MessageKind.SESSION_INIT,
                ):
                    continue

                text = self._extractor.extract(message)
                if text is None:
                    continue

                # Non-quiet: speak short messages immediately
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

            # Skip flush/drain if interrupted — go straight to next prompt
            if not self._interrupted:
                remaining = chunker.flush()
                if remaining:
                    await self._playback.enqueue(remaining)

                self._renderer.finalize()
                await self._playback.drain()
        finally:
            self._processing = False
            self._first_prompt = False

    def _handle_interrupt(self) -> None:
        if self._processing:
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self._interrupt()))
        else:
            self._running = False

    async def _interrupt(self) -> None:
        self._interrupted = True
        self._renderer.finalize()
        await self._playback.interrupt()
        await self._backend.interrupt()
        self._processing = False
        print("\n[Speech interrupted. Enter a new prompt.]")
