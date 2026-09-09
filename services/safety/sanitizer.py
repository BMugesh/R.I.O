"""Sensitive Data Sanitizer & Secret Scrubber for R.I.O.

Prevents credentials, API keys, tokens, and passwords from leaking into LLM prompts,
logs, or external response streams.
"""

import re
from typing import Any, Dict, List, Union


class Sanitizer:
    """Scrubs secrets, private tokens, and sensitive patterns."""

    SECRET_PATTERNS = [
        re.compile(r"(?:api_key|apikey|secret|token|password|auth|jwt)[\"':\s=]+([a-zA-Z0-9_\-\.]{16,})", re.IGNORECASE),
        re.compile(r"ghp_[a-zA-Z0-9]{36}"),  # GitHub PAT
        re.compile(r"gsk_[a-zA-Z0-9]{48}"),  # Groq Key
        re.compile(r"sk-[a-zA-Z0-9]{48}"),   # OpenAI Key
        re.compile(r"xoxb-[0-9]{11}-[0-9]{11}-[a-zA-Z0-9]{24}"),  # Slack Token
    ]

    @classmethod
    def scrub_text(cls, text: str) -> str:
        """Scrub secret tokens from string."""
        if not text:
            return ""
        sanitized = text
        for pattern in cls.SECRET_PATTERNS:
            sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
        return sanitized

    @classmethod
    def sanitize_payload(cls, payload: Any) -> Any:
        """Recursively scrub sensitive keys from dictionaries or lists."""
        if isinstance(payload, str):
            return cls.scrub_text(payload)
        elif isinstance(payload, dict):
            clean_dict = {}
            for k, v in payload.items():
                if any(sec in k.lower() for sec in ("secret", "password", "token", "api_key", "auth", "private_key")):
                    clean_dict[k] = "[REDACTED]"
                else:
                    clean_dict[k] = cls.sanitize_payload(v)
            return clean_dict
        elif isinstance(payload, list):
            return [cls.sanitize_payload(item) for item in payload]
        return payload
