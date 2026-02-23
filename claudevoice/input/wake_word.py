"""Wake word detection for voice input."""

import difflib
from typing import Optional


# "hey claude" and common Whisper mishearings
WAKE_VARIANTS = [
    "hey claude",
    "hey cloud",
    "hey clod",
    "hey claud",
    "hey clawed",
    "hey klaud",
    "hey klaude",
    "a claude",
    "hey, claude",
    "hey, cloud",
]

FUZZY_THRESHOLD = 0.7


class WakeWordDetector:
    """Detects 'hey claude' wake phrase in transcribed text."""

    def __init__(self, variants: list[str] | None = None):
        self._variants = [v.lower() for v in (variants or WAKE_VARIANTS)]

    def matches_wake_phrase(self, text: str) -> bool:
        """Check if text matches or starts with the wake phrase."""
        normalized = text.strip().lower()
        if not normalized:
            return False

        # Exact match against variants
        for variant in self._variants:
            if normalized == variant:
                return True
            if normalized.startswith(variant):
                return True

        # Fuzzy match: compare first few words against variants
        words = normalized.split()
        prefix = " ".join(words[:3])  # wake phrase is 2 words, allow 3 for filler
        for variant in self._variants:
            ratio = difflib.SequenceMatcher(None, prefix, variant).ratio()
            if ratio >= FUZZY_THRESHOLD:
                return True

        return False

    def extract_command(self, text: str) -> Optional[str]:
        """Extract command after wake phrase, if any.

        Returns the text after "hey claude, ..." or None if only wake phrase.
        """
        normalized = text.strip().lower()
        if not normalized:
            return None

        # Try each variant as a prefix
        for variant in self._variants:
            if normalized.startswith(variant):
                remainder = text.strip()[len(variant) :].strip()
                # Strip leading punctuation/filler
                remainder = remainder.lstrip(",.:;!? ")
                if remainder:
                    return remainder
                return None

        # Fuzzy match — can't reliably extract command
        return None
