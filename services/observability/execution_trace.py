"""Execution Trace Model for R.I.O. (Milestone 5).

Provides deep end-to-end execution audit trails for developer mode and telemetry.
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExecutionTrace(BaseModel):
    """Structured developer trace and telemetry container for an executed task."""

    task_id: str
    parent_task_id: Optional[str] = None
    goal: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    planning_time_ms: float = 0.0
    queue_time_ms: float = 0.0
    execution_time_ms: float = 0.0
    verification_time_ms: float = 0.0
    total_duration_ms: float = 0.0

    node_count: int = 0
    parallel_stages: int = 0
    max_concurrency: int = 1

    agents_used: List[str] = Field(default_factory=list)
    models_used: List[str] = Field(default_factory=list)
    compute_targets: List[str] = Field(default_factory=list)
    execution_device: str = "laptop-01"

    retries: int = 0
    replans: int = 0
    resource_usage: Dict[str, Any] = Field(default_factory=dict)
    verification_status: str = "verified"
    final_status: str = "completed"

    step_traces: List[Dict[str, Any]] = Field(default_factory=list)
