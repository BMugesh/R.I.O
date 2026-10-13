"""Bounded Exponential Backoff Retry Policy for R.I.O. (Milestone 5).

Prevents retry storms, limits retries by failure type, and applies bounded jitter.
"""

import random
from typing import Optional
from services.recovery.classifier import FailureType


class RetryPolicy:
    """Calculates retry eligibility and backoff intervals based on failure classification."""

    NON_RETRYABLE_TYPES = {
        FailureType.AUTHORIZATION,
        FailureType.SAFETY,
        FailureType.INVALID_INPUT,
    }

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 0.1,
        max_delay: float = 4.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter

    def should_retry(self, failure_type: FailureType, attempt: int, max_retries: Optional[int] = None) -> bool:
        """Determine if an execution failure should be retried."""
        limit = max_retries if max_retries is not None else self.max_retries
        if attempt >= limit:
            return False

        if failure_type in self.NON_RETRYABLE_TYPES:
            return False

        return True

    def compute_delay(self, attempt: int) -> float:
        """Calculate bounded backoff delay with jitter."""
        delay = self.initial_delay * (self.backoff_factor ** attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            delay = delay * (0.8 + 0.4 * random.random())

        return max(0.01, delay)
