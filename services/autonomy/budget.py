"""Autonomy Budget Constraints for R.I.O. (Milestone 5).

Strict upper bounds ensuring autonomous execution loops cannot diverge,
exhaust system resources, or run indefinitely.
"""

from typing import Optional
from pydantic import BaseModel, Field


class AutonomyBudget(BaseModel):
    """Budget ceilings and usage counters for an autonomous task."""

    max_runtime_ms: int = 60000        # Default: 60 seconds
    max_actions: int = 10              # Default: 10 atomic actions
    max_retries: int = 3
    max_replans: int = 2
    max_parallel_tasks: int = 4

    current_runtime_ms: int = 0
    current_actions: int = 0
    current_retries: int = 0
    current_replans: int = 0

    def can_continue(self) -> bool:
        """Check if remaining budget allows execution to proceed."""
        if self.current_runtime_ms >= self.max_runtime_ms:
            return False
        if self.current_actions >= self.max_actions:
            return False
        if self.current_retries >= self.max_retries:
            return False
        if self.current_replans >= self.max_replans:
            return False
        return True

    def record_action(self, duration_ms: int = 100) -> None:
        """Record consumption of one action and elapsed time."""
        self.current_actions += 1
        self.current_runtime_ms += duration_ms

    def record_retry(self) -> None:
        """Record consumption of one retry attempt."""
        self.current_retries += 1

    def record_replan(self) -> None:
        """Record consumption of one replanning cycle."""
        self.current_replans += 1
