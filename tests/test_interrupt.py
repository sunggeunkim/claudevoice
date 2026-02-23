"""Reproduce: input freezes after Ctrl+C speech interrupt.

This test simulates the full interrupt flow to identify where the hang occurs.
"""

import asyncio
import sys
import pytest
from typing import AsyncIterator, Optional

from claudevoice.app import ClaudeVoiceApp
from claudevoice.claude.base import ClaudeBackend
from claudevoice.claude.messages import ClaudeMessage, MessageKind
from claudevoice.input.base import InputSource
from claudevoice.tts.playback import NullPlaybackManager, PlaybackManager
from claudevoice.tts.base import TTSEngine


class SlowBackend(ClaudeBackend):
    """Backend that yields messages slowly, simulating Claude streaming."""

    def __init__(self):
        self._interrupted = False
        self.last_session_id = "test-session"

    async def send_prompt(
        self, prompt: str, *, session_id: str | None = None
    ) -> AsyncIterator[ClaudeMessage]:
        self._interrupted = False
        # Yield session init
        yield ClaudeMessage(kind=MessageKind.SESSION_INIT, session_id="test-session")
        # Yield text chunks slowly
        for i in range(20):
            if self._interrupted:
                return
            yield ClaudeMessage(
                kind=MessageKind.TEXT_CHUNK,
                text=f"This is sentence number {i}. ",
            )
            await asyncio.sleep(0.05)
        # Final result
        yield ClaudeMessage(
            kind=MessageKind.RESULT,
            text="Done",
            cost_usd=0.01,
            duration_ms=1000,
            session_id="test-session",
        )

    async def interrupt(self) -> None:
        self._interrupted = True

    async def close(self) -> None:
        pass


class ScriptedInput(InputSource):
    """Input source that returns pre-scripted prompts, tracking calls."""

    def __init__(self, prompts: list[str]):
        self._prompts = list(prompts)
        self._call_count = 0
        self.prompt_requested = asyncio.Event()

    @property
    def ready_message(self) -> str:
        return "Ready."

    async def get_prompt(self) -> Optional[str]:
        self._call_count += 1
        self.prompt_requested.set()
        if not self._prompts:
            return None
        return self._prompts.pop(0)


@pytest.mark.asyncio
async def test_input_available_after_interrupt():
    """After Ctrl+C interrupt, the app should request the next prompt.

    This is the core reproduction: if the app hangs after interrupt,
    get_prompt() is never called a second time.
    """
    backend = SlowBackend()
    playback = NullPlaybackManager()
    # Two prompts: first will be interrupted, second proves input works
    input_source = ScriptedInput(["hello", "world", None])

    app = ClaudeVoiceApp(
        backend=backend,
        playback=playback,
        input_source=input_source,
    )

    async def interrupt_during_processing():
        # Wait for first prompt to start processing
        await asyncio.sleep(0.15)
        # Simulate Ctrl+C
        app._handle_interrupt()

    async def run_with_timeout():
        interrupt_task = asyncio.create_task(interrupt_during_processing())
        try:
            await asyncio.wait_for(app.run(), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail(
                "App hung after interrupt — get_prompt() was never called again. "
                f"get_prompt call count: {input_source._call_count}, "
                f"processing: {app._processing}, interrupted: {app._interrupted}"
            )
        finally:
            interrupt_task.cancel()
            try:
                await interrupt_task
            except asyncio.CancelledError:
                pass

    await run_with_timeout()

    # The input source should have been called 4 times:
    # 1. "hello" (processed, then interrupted)
    # 2. "world" (processed normally)
    # 3. None (exit)
    # If it hung, call_count would be 1.
    assert input_source._call_count >= 3, (
        f"Expected at least 3 get_prompt() calls but got {input_source._call_count}. "
        "App likely hung after interrupt."
    )


@pytest.mark.asyncio
async def test_interrupt_does_not_block_on_drain():
    """After interrupt, _process_prompt should not block on playback.drain()."""
    backend = SlowBackend()
    playback = NullPlaybackManager()
    input_source = ScriptedInput(["hello", None])

    app = ClaudeVoiceApp(
        backend=backend,
        playback=playback,
        input_source=input_source,
    )

    async def interrupt_quickly():
        await asyncio.sleep(0.1)
        app._handle_interrupt()

    interrupt_task = asyncio.create_task(interrupt_quickly())

    try:
        await asyncio.wait_for(app.run(), timeout=3.0)
    except asyncio.TimeoutError:
        pytest.fail("App hung — likely blocked on drain() after interrupt")
    finally:
        interrupt_task.cancel()
        try:
            await interrupt_task
        except asyncio.CancelledError:
            pass

    assert input_source._call_count >= 2


@pytest.mark.asyncio
async def test_interrupt_then_normal_prompt():
    """An interrupted prompt followed by a normal prompt should both complete."""
    backend = SlowBackend()
    playback = NullPlaybackManager()
    results = []

    class TrackingInput(InputSource):
        def __init__(self):
            self._prompts = ["first", "second", None]
            self.call_count = 0

        @property
        def ready_message(self) -> str:
            return "Ready."

        async def get_prompt(self) -> Optional[str]:
            self.call_count += 1
            results.append(f"prompt_requested_{self.call_count}")
            if not self._prompts:
                return None
            return self._prompts.pop(0)

    input_source = TrackingInput()
    app = ClaudeVoiceApp(
        backend=backend,
        playback=playback,
        input_source=input_source,
    )

    async def interrupt_first_prompt():
        await asyncio.sleep(0.15)
        app._handle_interrupt()

    interrupt_task = asyncio.create_task(interrupt_first_prompt())

    try:
        await asyncio.wait_for(app.run(), timeout=10.0)
    except asyncio.TimeoutError:
        pytest.fail(
            f"App hung. Results so far: {results}, "
            f"call_count: {input_source.call_count}"
        )
    finally:
        interrupt_task.cancel()
        try:
            await interrupt_task
        except asyncio.CancelledError:
            pass

    # Should have requested 3 prompts: "first", "second", None
    assert input_source.call_count == 3, (
        f"Expected 3 prompt requests, got {input_source.call_count}. "
        f"Results: {results}"
    )


# ---------- Realistic tests using real subprocess + threaded input ----------


class SubprocessStreamBackend(ClaudeBackend):
    """Backend that runs a real subprocess emitting NDJSON, like claude would."""

    def __init__(self):
        self._process: Optional[asyncio.subprocess.Process] = None
        self.last_session_id = "test-session"

    async def send_prompt(
        self, prompt: str, *, session_id: str | None = None
    ) -> AsyncIterator[ClaudeMessage]:
        import json

        # Use a python subprocess that prints NDJSON lines slowly
        script = (
            "import time, json, sys\n"
            "for i in range(50):\n"
            "    print(json.dumps({'type':'text_chunk','i':i}), flush=True)\n"
            "    time.sleep(0.05)\n"
            "print(json.dumps({'type':'done'}), flush=True)\n"
        )
        self._process = await asyncio.create_subprocess_exec(
            sys.executable, "-c", script,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )

        while True:
            line = await self._process.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            try:
                import json as j
                data = j.loads(text)
            except Exception:
                continue
            if data.get("type") == "text_chunk":
                yield ClaudeMessage(
                    kind=MessageKind.TEXT_CHUNK,
                    text=f"Sentence {data['i']}. ",
                )

        returncode = await self._process.wait()
        self._process = None
        if returncode != 0:
            yield ClaudeMessage(
                kind=MessageKind.ERROR,
                text=f"Process exited with code {returncode}",
                is_error=True,
            )

    async def interrupt(self) -> None:
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                self._process.kill()

    async def close(self) -> None:
        await self.interrupt()


class ThreadedInput(InputSource):
    """Input source using run_in_executor like the real RichInput does."""

    def __init__(self, prompts: list[Optional[str]]):
        self._prompts = list(prompts)
        self._idx = 0
        self.call_count = 0

    @property
    def ready_message(self) -> str:
        return "Ready."

    async def get_prompt(self) -> Optional[str]:
        loop = asyncio.get_event_loop()
        self.call_count += 1
        # Simulate threaded input() — blocks in executor briefly
        result = await loop.run_in_executor(None, self._blocking_input)
        return result

    def _blocking_input(self) -> Optional[str]:
        if self._idx >= len(self._prompts):
            return None
        prompt = self._prompts[self._idx]
        self._idx += 1
        return prompt


class MockTTSEngine(TTSEngine):
    """TTS engine that simulates slow speech synthesis."""

    def __init__(self, speak_delay: float = 0.1):
        self._delay = speak_delay
        self._speaking = False
        self._stop = False

    async def initialize(self) -> None:
        pass

    async def speak(self, text: str) -> None:
        self._speaking = True
        self._stop = False
        try:
            # Simulate slow speech in small increments so stop works
            elapsed = 0.0
            while elapsed < self._delay and not self._stop:
                await asyncio.sleep(0.01)
                elapsed += 0.01
        finally:
            self._speaking = False

    async def stop(self) -> None:
        self._stop = True

    async def shutdown(self) -> None:
        await self.stop()

    @property
    def is_speaking(self) -> bool:
        return self._speaking


@pytest.mark.asyncio
async def test_interrupt_with_real_subprocess():
    """Interrupt with a real subprocess — tests that the async generator
    properly terminates after the subprocess is killed."""
    backend = SubprocessStreamBackend()
    playback = NullPlaybackManager()
    input_source = ScriptedInput(["hello", "world", None])

    app = ClaudeVoiceApp(
        backend=backend,
        playback=playback,
        input_source=input_source,
    )

    async def interrupt_during_processing():
        await asyncio.sleep(0.2)
        app._handle_interrupt()

    interrupt_task = asyncio.create_task(interrupt_during_processing())

    try:
        await asyncio.wait_for(app.run(), timeout=10.0)
    except asyncio.TimeoutError:
        pytest.fail(
            f"App hung with real subprocess after interrupt. "
            f"get_prompt calls: {input_source._call_count}, "
            f"processing: {app._processing}"
        )
    finally:
        interrupt_task.cancel()
        try:
            await interrupt_task
        except asyncio.CancelledError:
            pass

    assert input_source._call_count >= 3, (
        f"Expected 3+ get_prompt() calls, got {input_source._call_count}"
    )


@pytest.mark.asyncio
async def test_interrupt_with_threaded_input():
    """Interrupt with threaded input (like real RichInput uses)."""
    backend = SlowBackend()
    playback = NullPlaybackManager()
    input_source = ThreadedInput(["hello", "world", None])

    app = ClaudeVoiceApp(
        backend=backend,
        playback=playback,
        input_source=input_source,
    )

    async def interrupt_during_processing():
        await asyncio.sleep(0.15)
        app._handle_interrupt()

    interrupt_task = asyncio.create_task(interrupt_during_processing())

    try:
        await asyncio.wait_for(app.run(), timeout=10.0)
    except asyncio.TimeoutError:
        pytest.fail(
            f"App hung with threaded input after interrupt. "
            f"get_prompt calls: {input_source.call_count}, "
            f"processing: {app._processing}"
        )
    finally:
        interrupt_task.cancel()
        try:
            await interrupt_task
        except asyncio.CancelledError:
            pass

    assert input_source.call_count >= 3, (
        f"Expected 3+ get_prompt() calls, got {input_source.call_count}"
    )


# ---------- Isolated stdin/input() tests ----------

import signal


@pytest.mark.asyncio
async def test_input_in_executor_after_sigint_handler():
    """Test that input() in a thread executor works after asyncio SIGINT handler.

    This reproduces the real scenario: asyncio overrides SIGINT, then
    input() is called via run_in_executor. If the terminal or
    _PyOS_ReadlineLock is corrupted, input() will hang.
    """
    import os

    if sys.platform == "win32":
        pytest.skip("PTY not available on Windows")

    # Create a pseudo-terminal to feed input
    master_fd, slave_fd = os.openpty()
    old_stdin = sys.stdin

    try:
        # Redirect stdin to the PTY slave
        sys.stdin = os.fdopen(slave_fd, "r")
        loop = asyncio.get_event_loop()

        # Simulate what the app does: set a SIGINT handler
        handler_called = False

        def sigint_handler():
            nonlocal handler_called
            handler_called = True

        loop.add_signal_handler(signal.SIGINT, sigint_handler)

        # Simulate Ctrl+C by calling the handler directly
        sigint_handler()
        assert handler_called

        # Now try to read input via executor (like RichInput does)
        # Write a line to the PTY master so input() has something to read
        os.write(master_fd, b"test prompt\n")

        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: input("")),
                timeout=3.0,
            )
        except asyncio.TimeoutError:
            pytest.fail(
                "input() hung after SIGINT handler was called. "
                "This reproduces the Ctrl+C freeze bug."
            )

        assert result == "test prompt"

    finally:
        sys.stdin = old_stdin
        loop.remove_signal_handler(signal.SIGINT)
        os.close(master_fd)


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="Demonstrates CPython _PyOS_ReadlineLock deadlock — root cause of #2",
    strict=True,
)
async def test_concurrent_input_deadlock():
    """Test the _PyOS_ReadlineLock deadlock scenario.

    If input() is running in one thread and we call input() in another
    thread, the second call deadlocks on _PyOS_ReadlineLock.
    This tests whether our interrupt flow could trigger this.
    """
    import os

    if sys.platform == "win32":
        pytest.skip("PTY not available on Windows")

    master_fd, slave_fd = os.openpty()
    old_stdin = sys.stdin

    try:
        sys.stdin = os.fdopen(slave_fd, "r")
        loop = asyncio.get_event_loop()

        # Start a first input() call in the executor
        # DON'T feed a line — this thread will block holding _PyOS_ReadlineLock
        zombie_future = loop.run_in_executor(
            None, lambda: input("")
        )

        # Give the thread time to start and acquire the lock
        await asyncio.sleep(0.2)

        # Start a second concurrent input() — this should deadlock
        # if _PyOS_ReadlineLock is held by the first thread
        os.write(master_fd, b"concurrent\n")
        try:
            concurrent_result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: input("")),
                timeout=2.0,
            )
            # If we get here without timeout, no deadlock
        except asyncio.TimeoutError:
            # DEADLOCK REPRODUCED
            pytest.fail(
                "DEADLOCK REPRODUCED: Concurrent input() call hung because "
                "the first input() thread holds _PyOS_ReadlineLock. "
                "This is the root cause of the Ctrl+C freeze if a zombie "
                "input() thread survives after interrupt."
            )
        finally:
            # Clean up: feed lines to unblock any blocked threads
            try:
                os.write(master_fd, b"cleanup1\n")
                os.write(master_fd, b"cleanup2\n")
            except OSError:
                pass
            try:
                await asyncio.wait_for(zombie_future, timeout=2.0)
            except (asyncio.TimeoutError, EOFError, OSError):
                pass

    finally:
        sys.stdin = old_stdin
        os.close(master_fd)


@pytest.mark.asyncio
async def test_interrupt_with_real_playback():
    """Interrupt with real PlaybackManager and mock TTS engine."""
    backend = SlowBackend()
    engine = MockTTSEngine(speak_delay=0.05)
    playback = PlaybackManager(engine)
    input_source = ScriptedInput(["hello", "world", None])

    app = ClaudeVoiceApp(
        backend=backend,
        playback=playback,
        input_source=input_source,
    )

    async def interrupt_during_processing():
        # Wait until processing has started
        while not app._processing:
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.1)
        app._handle_interrupt()

    interrupt_task = asyncio.create_task(interrupt_during_processing())

    try:
        await asyncio.wait_for(app.run(), timeout=10.0)
    except asyncio.TimeoutError:
        pytest.fail(
            f"App hung with real playback after interrupt. "
            f"get_prompt calls: {input_source._call_count}, "
            f"processing: {app._processing}"
        )
    finally:
        interrupt_task.cancel()
        try:
            await interrupt_task
        except asyncio.CancelledError:
            pass

    assert input_source._call_count >= 3, (
        f"Expected 3+ get_prompt() calls, got {input_source._call_count}"
    )


@pytest.mark.asyncio
async def test_interrupt_full_realistic_stack():
    """Full realistic test: real subprocess + real playback + threaded input."""
    backend = SubprocessStreamBackend()
    engine = MockTTSEngine(speak_delay=0.05)
    playback = PlaybackManager(engine)
    input_source = ThreadedInput(["hello", "world", None])

    app = ClaudeVoiceApp(
        backend=backend,
        playback=playback,
        input_source=input_source,
    )

    async def interrupt_during_processing():
        while not app._processing:
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.15)
        app._handle_interrupt()

    interrupt_task = asyncio.create_task(interrupt_during_processing())

    try:
        await asyncio.wait_for(app.run(), timeout=10.0)
    except asyncio.TimeoutError:
        pytest.fail(
            f"App hung with full stack after interrupt. "
            f"get_prompt calls: {input_source.call_count}, "
            f"processing: {app._processing}"
        )
    finally:
        interrupt_task.cancel()
        try:
            await interrupt_task
        except asyncio.CancelledError:
            pass

    assert input_source.call_count >= 3, (
        f"Expected 3+ get_prompt() calls, got {input_source.call_count}"
    )
