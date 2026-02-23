import asyncio
import json
from typing import AsyncIterator, Optional

from claudevoice.claude.base import ClaudeBackend
from claudevoice.claude.messages import ClaudeMessage, MessageKind


def summarize_tool(name: str, input_data: dict) -> str:
    """Create a human-friendly spoken summary of a tool invocation."""
    summaries = {
        "Read": lambda d: f"Reading file {d.get('file_path', 'unknown')}",
        "Write": lambda d: f"Writing file {d.get('file_path', 'unknown')}",
        "Edit": lambda d: f"Editing file {d.get('file_path', 'unknown')}",
        "Bash": lambda d: f"Running command: {d.get('description') or str(d.get('command', 'unknown'))[:60]}",
        "Glob": lambda d: f"Searching for files matching {d.get('pattern', 'unknown')}",
        "Grep": lambda d: f"Searching for {d.get('pattern', 'unknown')}",
        "WebFetch": lambda d: "Fetching a web page",
        "WebSearch": lambda d: f"Searching the web for {d.get('query', 'unknown')}",
        "Task": lambda d: f"Launching agent: {d.get('description', 'subtask')}",
        "NotebookEdit": lambda d: "Editing notebook",
    }
    fn = summaries.get(name, lambda d: f"Using tool {name}")
    return fn(input_data)


def parse_ndjson_line(data: dict) -> list[ClaudeMessage]:
    """Parse a single NDJSON object from claude stream-json into ClaudeMessages."""
    results = []
    msg_type = data.get("type", "")

    if msg_type == "assistant":
        message = data.get("message", {})
        content = message.get("content", [])
        if isinstance(content, list):
            for block in content:
                block_type = block.get("type", "")
                if block_type == "text":
                    text = block.get("text", "")
                    if text.strip():
                        results.append(ClaudeMessage(
                            kind=MessageKind.TEXT_CHUNK,
                            text=text,
                            raw=data,
                        ))
                elif block_type == "tool_use":
                    name = block.get("name", "unknown")
                    inp = block.get("input", {})
                    summary = summarize_tool(name, inp)
                    results.append(ClaudeMessage(
                        kind=MessageKind.TOOL_START,
                        text=summary,
                        tool_name=name,
                        tool_input_summary=summary,
                        raw=data,
                    ))
                elif block_type == "thinking":
                    results.append(ClaudeMessage(
                        kind=MessageKind.THINKING,
                        text=block.get("thinking", ""),
                        raw=data,
                    ))

    elif msg_type == "user":
        message = data.get("message", {})
        content = message.get("content", [])
        if isinstance(content, list):
            for block in content:
                if block.get("type") == "tool_result":
                    is_error = block.get("is_error", False)
                    tool_id = block.get("tool_use_id", "")
                    if is_error:
                        error_content = block.get("content", "")
                        if isinstance(error_content, list):
                            error_text = " ".join(
                                b.get("text", "") for b in error_content
                                if b.get("type") == "text"
                            )
                        else:
                            error_text = str(error_content)
                        results.append(ClaudeMessage(
                            kind=MessageKind.ERROR,
                            text=error_text,
                            is_error=True,
                            raw=data,
                        ))

    elif msg_type == "system":
        subtype = data.get("subtype", "")
        if subtype == "init":
            results.append(ClaudeMessage(
                kind=MessageKind.SESSION_INIT,
                session_id=data.get("session_id"),
                raw=data,
            ))

    elif msg_type == "result":
        results.append(ClaudeMessage(
            kind=MessageKind.RESULT,
            text=data.get("result", ""),
            is_error=data.get("is_error", False),
            cost_usd=data.get("total_cost_usd"),
            duration_ms=data.get("duration_ms"),
            session_id=data.get("session_id"),
            raw=data,
        ))

    return results


class SubprocessBackend(ClaudeBackend):
    """Claude Code backend using subprocess + stream-json NDJSON."""

    def __init__(self, claude_path: str = "claude", model: Optional[str] = None):
        self._claude_path = claude_path
        self._model = model
        self._process: Optional[asyncio.subprocess.Process] = None
        self._last_session_id: Optional[str] = None

    @property
    def last_session_id(self) -> Optional[str]:
        return self._last_session_id

    async def send_prompt(
        self, prompt: str, *, session_id: str | None = None
    ) -> AsyncIterator[ClaudeMessage]:
        resume_id = session_id or self._last_session_id
        cmd = [
            self._claude_path, "-p",
            "--output-format", "stream-json",
            "--verbose",
        ]
        if resume_id:
            cmd.extend(["--resume", resume_id])
        cmd.append(prompt)
        if self._model:
            cmd.extend(["--model", self._model])

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
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
                data = json.loads(text)
            except json.JSONDecodeError:
                continue

            for msg in parse_ndjson_line(data):
                if msg.session_id:
                    self._last_session_id = msg.session_id
                yield msg

        returncode = await self._process.wait()
        if returncode != 0:
            yield ClaudeMessage(
                kind=MessageKind.ERROR,
                text=f"Claude process exited with code {returncode}",
                is_error=True,
            )
        self._process = None

    async def interrupt(self) -> None:
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                self._process.kill()

    async def close(self) -> None:
        await self.interrupt()
