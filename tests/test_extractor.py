from claudevoice.claude.messages import ClaudeMessage, MessageKind
from claudevoice.pipeline.extractor import MessageExtractor


def test_text_chunk_extracted():
    msg = ClaudeMessage(kind=MessageKind.TEXT_CHUNK, text="Hello world.")
    assert MessageExtractor().extract(msg) == "Hello world."


def test_text_chunk_empty_skipped():
    msg = ClaudeMessage(kind=MessageKind.TEXT_CHUNK, text="   ")
    assert MessageExtractor().extract(msg) is None


def test_tool_start_enabled():
    msg = ClaudeMessage(
        kind=MessageKind.TOOL_START,
        text="Reading file auth.py",
        tool_name="Read",
    )
    result = MessageExtractor(speak_tools=True).extract(msg)
    assert result == "Reading file auth.py"


def test_tool_start_disabled():
    msg = ClaudeMessage(
        kind=MessageKind.TOOL_START,
        text="Reading file auth.py",
        tool_name="Read",
    )
    assert MessageExtractor(speak_tools=False).extract(msg) is None


def test_error_message():
    msg = ClaudeMessage(kind=MessageKind.ERROR, text="file not found", is_error=True)
    result = MessageExtractor().extract(msg)
    assert result == "Error: file not found"


def test_result_success():
    msg = ClaudeMessage(
        kind=MessageKind.RESULT,
        text="Done",
        cost_usd=0.05,
        duration_ms=3000,
    )
    result = MessageExtractor().extract(msg)
    assert "Task complete." in result
    assert "0.0500 dollars" in result
    assert "3.0 seconds" in result


def test_result_no_cost():
    msg = ClaudeMessage(kind=MessageKind.RESULT, text="Done")
    result = MessageExtractor(speak_cost=False).extract(msg)
    assert "Task complete." in result
    assert "dollars" not in result


def test_result_error():
    msg = ClaudeMessage(
        kind=MessageKind.RESULT,
        text="Something went wrong",
        is_error=True,
    )
    result = MessageExtractor().extract(msg)
    assert "Task failed" in result


def test_session_init():
    msg = ClaudeMessage(kind=MessageKind.SESSION_INIT)
    assert MessageExtractor().extract(msg) == "Connected to Claude."


def test_thinking_skipped():
    msg = ClaudeMessage(kind=MessageKind.THINKING, text="Let me think...")
    assert MessageExtractor().extract(msg) is None
