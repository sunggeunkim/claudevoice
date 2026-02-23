import re
from typing import Optional


class SentenceChunker:
    """Accumulates text and yields complete sentences for TTS.

    Buffers incoming text and emits chunks at sentence boundaries,
    so the user hears the first sentence while Claude is still generating.
    """

    SENTENCE_END = re.compile(r'(?<=[.!?:;])\s+')

    def __init__(self, min_chunk_length: int = 20, max_chunk_length: int = 500):
        self._buffer = ""
        self.min_chunk_length = min_chunk_length
        self.max_chunk_length = max_chunk_length

    def feed(self, text: str) -> list[str]:
        """Feed text and return list of complete sentence chunks."""
        self._buffer += text
        chunks = []

        while True:
            match = self.SENTENCE_END.search(self._buffer)
            if match:
                chunk = self._buffer[:match.start() + 1].strip()
                self._buffer = self._buffer[match.end():]
                if chunk:
                    chunks.append(chunk)
            elif len(self._buffer) > self.max_chunk_length:
                break_at = self._buffer.rfind(" ", 0, self.max_chunk_length)
                if break_at == -1:
                    break_at = self.max_chunk_length
                chunk = self._buffer[:break_at].strip()
                self._buffer = self._buffer[break_at:].lstrip()
                if chunk:
                    chunks.append(chunk)
            else:
                break

        return chunks

    def flush(self) -> Optional[str]:
        """Return any remaining buffered text."""
        remaining = self._buffer.strip()
        self._buffer = ""
        return remaining if remaining else None
