import json

from claudevoice.claude.messages import MessageKind
from claudevoice.claude.subprocess_backend import parse_ndjson_line


def test_parse_system_init():
    data = {
        "type": "system",
        "subtype": "init",
        "session_id": "abc-123",
        "tools": ["Bash", "Read"],
        "model": "claude-sonnet-4-6",
    }
    msgs = parse_ndjson_line(data)
    assert len(msgs) == 1
    assert msgs[0].kind == MessageKind.SESSION_INIT
    assert msgs[0].session_id == "abc-123"


def test_parse_assistant_text():
    data = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello! How can I help?"}],
        },
    }
    msgs = parse_ndjson_line(data)
    assert len(msgs) == 1
    assert msgs[0].kind == MessageKind.TEXT_CHUNK
    assert msgs[0].text == "Hello! How can I help?"


def test_parse_tool_use_bash():
    data = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "tool-1",
                    "name": "Bash",
                    "input": {"command": "git status", "description": "Check git status"},
                }
            ],
        },
    }
    msgs = parse_ndjson_line(data)
    assert len(msgs) == 1
    assert msgs[0].kind == MessageKind.TOOL_START
    assert msgs[0].tool_name == "Bash"
    assert "Check git status" in msgs[0].text


def test_parse_tool_use_read():
    data = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "tool-2",
                    "name": "Read",
                    "input": {"file_path": "/home/user/auth.py"},
                }
            ],
        },
    }
    msgs = parse_ndjson_line(data)
    assert len(msgs) == 1
    assert "Reading file /home/user/auth.py" in msgs[0].text


def test_parse_tool_result_error():
    data = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tool-1",
                    "is_error": True,
                    "content": [{"type": "text", "text": "Permission denied"}],
                }
            ],
        },
    }
    msgs = parse_ndjson_line(data)
    assert len(msgs) == 1
    assert msgs[0].kind == MessageKind.ERROR
    assert "Permission denied" in msgs[0].text


def test_parse_result_success():
    data = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": "Task done",
        "total_cost_usd": 0.0123,
        "duration_ms": 4500,
        "session_id": "abc-123",
    }
    msgs = parse_ndjson_line(data)
    assert len(msgs) == 1
    assert msgs[0].kind == MessageKind.RESULT
    assert msgs[0].cost_usd == 0.0123
    assert msgs[0].duration_ms == 4500
    assert not msgs[0].is_error


def test_parse_result_error():
    data = {
        "type": "result",
        "subtype": "error_max_turns",
        "is_error": True,
        "result": "Max turns reached",
    }
    msgs = parse_ndjson_line(data)
    assert len(msgs) == 1
    assert msgs[0].kind == MessageKind.RESULT
    assert msgs[0].is_error


def test_parse_thinking_block():
    data = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "thinking", "thinking": "Let me consider..."}],
        },
    }
    msgs = parse_ndjson_line(data)
    assert len(msgs) == 1
    assert msgs[0].kind == MessageKind.THINKING


def test_parse_mixed_content():
    data = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Let me check that."},
                {
                    "type": "tool_use",
                    "id": "tool-1",
                    "name": "Read",
                    "input": {"file_path": "/tmp/test.py"},
                },
            ],
        },
    }
    msgs = parse_ndjson_line(data)
    assert len(msgs) == 2
    assert msgs[0].kind == MessageKind.TEXT_CHUNK
    assert msgs[1].kind == MessageKind.TOOL_START


def test_parse_full_fixture():
    """Parse the sample_stream.jsonl fixture end-to-end."""
    import os

    fixture_path = os.path.join(
        os.path.dirname(__file__), "fixtures", "sample_stream.jsonl"
    )
    all_messages = []
    with open(fixture_path) as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                all_messages.extend(parse_ndjson_line(data))

    kinds = [m.kind for m in all_messages]
    assert MessageKind.SESSION_INIT in kinds
    assert MessageKind.TEXT_CHUNK in kinds
    assert MessageKind.TOOL_START in kinds
    assert MessageKind.RESULT in kinds
