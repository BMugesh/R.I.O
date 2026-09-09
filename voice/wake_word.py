"""Local Wake-Word Detection Engine for R.I.O.

Guarantees 100% local wake-word trigger detection.
Zero audio is streamed to external cloud or LLMs during continuous listening.
"""

import logging
import re
from typing import List, Optional, Tuple

logger = logging.getLogger("rio.voice.wake_word")


class WakeWordDetector:
    """Local wake-word detector matching trigger keywords without cloud streaming."""

    DEFAULT_WAKE_WORDS = [
        "rio",
        "hey rio",
        "hi rio",
        "ok rio",
        "hello rio",
        "r.i.o.",
        "friday",
    ]

    def __init__(self, wake_words: Optional[List[str]] = None, sensitivity: float = 0.5):
        self.wake_words = [w.lower().strip() for w in (wake_words or self.DEFAULT_WAKE_WORDS)]
        self.sensitivity = sensitivity
        sorted_words = sorted(self.wake_words, key=len, reverse=True)
        self._patterns = [
            (w, re.compile(rf"^\s*\b{re.escape(w)}\b[,\s:]*(.*)", re.IGNORECASE))
            for w in sorted_words
        ]

    def check_text_for_wake_word(self, text: str) -> Tuple[bool, Optional[str], str]:
        """Inspect transcription text for wake-word trigger.

        Returns:
            (is_detected: bool, matched_wake_word: Optional[str], command_remainder: str)
        """
        cleaned = text.strip()
        for w, pattern in self._patterns:
            match = pattern.match(cleaned)
            if match:
                remainder = match.group(1).strip()
                logger.info(f"Wake word '{w}' detected! Command remainder: '{remainder}'")
                return True, w, remainder

        # Check if the text is simply the wake word alone
        lower_text = cleaned.lower()
        for w in self.wake_words:
            if lower_text == w:
                return True, w, ""

        return False, None, cleaned

    def strip_wake_word(self, full_text: str) -> str:
        """Strip detected wake word prefix from text command."""
        _, _, remainder = self.check_text_for_wake_word(full_text)
        return remainder if remainder else full_text
