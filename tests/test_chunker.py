from claudevoice.pipeline.chunker import SentenceChunker


def test_single_sentence():
    c = SentenceChunker()
    result = c.feed("Hello world. ")
    assert len(result) == 1
    assert result[0] == "Hello world."


def test_multiple_sentences():
    c = SentenceChunker(min_chunk_length=5)
    result = c.feed("First sentence. Second sentence. ")
    assert len(result) == 2
    assert result[0] == "First sentence."
    assert result[1] == "Second sentence."


def test_partial_sentence_buffered():
    c = SentenceChunker()
    assert c.feed("Hello wor") == []
    result = c.feed("ld. Next sentence starts")
    assert len(result) == 1
    assert result[0] == "Hello world."


def test_flush_remaining():
    c = SentenceChunker()
    c.feed("No period here")
    assert c.flush() == "No period here"


def test_flush_empty():
    c = SentenceChunker()
    assert c.flush() is None


def test_long_text_force_break():
    c = SentenceChunker(max_chunk_length=50)
    long_text = "word " * 30  # 150 chars, no sentence end
    result = c.feed(long_text)
    assert len(result) >= 1
    for chunk in result:
        assert len(chunk) <= 55  # some tolerance for word boundaries


def test_question_mark_splits():
    c = SentenceChunker(min_chunk_length=5)
    result = c.feed("What is this? I don't know. ")
    assert len(result) == 2


def test_exclamation_splits():
    c = SentenceChunker(min_chunk_length=5)
    result = c.feed("Watch out! Be careful. ")
    assert len(result) == 2
