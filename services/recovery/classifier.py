"""Failure Classifier for R.I.O. (Milestone 5).

Classifies execution errors into actionable taxonomy categories to determine
recoverability, retry candidacy, and fallback strategies.
"""

from enum import Enum
import re
from typing import Any, Dict, Optional


class FailureType(str, Enum):
    TRANSIENT = "transient"          # Timeouts, 429 rate limit, 503 unavailable
    RESOURCE = "resource"            # VRAM exhausted, OOM, memory error
    NETWORK = "network"              # Connection reset, socket error, DNS failed
    AUTHORIZATION = "authorization"  # 401, 403, permission denied, access blocked
    CAPABILITY = "capability"        # Tool missing, unsupported action, missing agent
    INVALID_INPUT = "invalid_input"  # Validation error, bad argument, malformed JSON
    TOOL = "tool"                    # External executable non-zero exit, subprocess error
    MODEL = "model"                  # Context length exceeded, model output parsing failure
    DEVICE = "device"                # Device offline, disconnected, unreachable
    VERIFICATION = "verification"    # Expected state not verified by evidence
    SAFETY = "safety"                # Policy engine violation, approval denied
    UNKNOWN = "unknown"              # Unrecognized exception


class FailureClassifier:
    """Analyzes exceptions and error messages to classify the failure."""

    @classmethod
    def classify(cls, error: Any, context: Optional[Dict[str, Any]] = None) -> FailureType:
        """Classify an exception or error string into FailureType."""
        err_str = str(error).lower()

        # 1. Safety & Permissions
        if any(p in err_str for p in ("denied", "forbidden", "unauthorized", "approval denied", "401", "403", "permission")):
            if "approval" in err_str or "policy" in err_str:
                return FailureType.SAFETY
            return FailureType.AUTHORIZATION

        # 2. Resource & Memory
        if any(p in err_str for p in ("out of memory", "oom", "cuda error: out of memory", "vram", "insufficient memory", "memoryerror")):
            return FailureType.RESOURCE

        # 3. Network & Connection
        if any(p in err_str for p in ("connectionrefused", "connection refused", "connecterror", "connection reset", "name or service not known", "dns", "socket", "refused")):
            return FailureType.NETWORK

        # 4. Transient / Timeout
        if any(p in err_str for p in ("timeout", "timed out", "rate limit", "429", "503", "temporarily unavailable", "busy")):
            return FailureType.TRANSIENT

        # 5. Verification failure
        if "verification failed" in err_str or "evidence not verified" in err_str or "expected state" in err_str:
            return FailureType.VERIFICATION

        # 6. Device unreachable
        if any(p in err_str for p in ("device offline", "device unreachable", "device disconnected", "adb not found")):
            return FailureType.DEVICE

        # 7. Capability & Tools
        if any(p in err_str for p in ("not found", "command not found", "unsupported action", "no such tool")):
            return FailureType.CAPABILITY

        # 8. Invalid input
        if any(p in err_str for p in ("invalid argument", "bad request", "validation error", "malformed")):
            return FailureType.INVALID_INPUT

        return FailureType.UNKNOWN
