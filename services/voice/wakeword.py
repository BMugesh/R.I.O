"""Configurable Local Wake-Word Detector for R.I.O. (Milestone 5.x).

Guarantees 100% local keyword pattern matching.
Zero microphone audio is streamed to the cloud while waiting for the wake phrase.
"""

import logging
import os
import re
from typing import List, Optional, Tuple

logger = logging.getLogger("rio.voice.wakeword")


class WakeWordDetector:
    """Detects configurable wake phrase ("Hey RIO") and optional aliases locally."""

    DEFAULT_WAKE_PHRASE = "Hey RIO"
    DEFAULT_ALIASES = ["Wake up RIO", "RIO", "Friday", "Hello RIO", "Hi RIO"]

    def __init__(
        self,
        wake_phrase: Optional[str] = None,
        aliases: Optional[List[str]] = None,
        sensitivity: float = 0.5,
    ):
        # 1. Resolve wake phrase from args or environment
        env_phrase = os.getenv("RIO_WAKE_PHRASE")
        self.wake_phrase = (wake_phrase or env_phrase or self.DEFAULT_WAKE_PHRASE).strip()

        # 2. Resolve aliases from args or environment
        env_aliases = os.getenv("RIO_WAKE_ALIASES")
        if aliases is not None:
            self.aliases = [a.strip() for a in aliases if a.strip()]
        elif env_aliases:
            self.aliases = [a.strip() for a in env_aliases.split(",") if a.strip()]
        else:
            self.aliases = list(self.DEFAULT_ALIASES)

        self.sensitivity = sensitivity

        # Combine and order by descending length for greedy matching
        all_phrases = [self.wake_phrase] + self.aliases
        unique_phrases = []
        for p in all_phrases:
            p_clean = p.lower().strip()
            if p_clean and p_clean not in unique_phrases:
                unique_phrases.append(p_clean)

        self.registered_phrases = sorted(unique_phrases, key=len, reverse=True)

        # Build regex patterns
        self._patterns = [
            (phrase, re.compile(rf"^\s*\b{re.escape(phrase)}\b[,\s:]*(.*)", re.IGNORECASE))
            for phrase in self.registered_phrases
        ]

    def check_text(self, text: str) -> Tuple[bool, Optional[str], str]:
        """Inspect text for wake phrase match.
        
        Returns:
            (is_detected: bool, matched_phrase: Optional[str], remainder_command: str)
        """
        if not text:
            return False, None, ""

        cleaned = text.strip()

        for phrase, pattern in self._patterns:
            match = pattern.match(cleaned)
            if match:
                raw_rem = match.group(1).strip()
                if raw_rem in (".", "!", "?", ",", ";", ":"):
                    clean_remainder = ""
                else:
                    clean_remainder = re.sub(r"^[\s,.:;]+", "", raw_rem).strip()
                logger.info(f"Local wake phrase '{phrase}' matched. Remainder: '{clean_remainder}'")
                return True, phrase, clean_remainder

        # Standalone wake phrase match with trailing punctuation stripped
        lower = cleaned.lower().rstrip(".,!?")
        for phrase in self.registered_phrases:
            if lower == phrase:
                return True, phrase, ""

        return False, None, cleaned

    def strip_wake_phrase(self, text: str) -> str:
        """Remove wake phrase prefix if present."""
        is_detected, _, remainder = self.check_text(text)
        return remainder if is_detected else text
