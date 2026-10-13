"""Execution Context Model for R.I.O. (Milestone 5).

Carries task and step runtime environment, device origin, security permissions,
priority, and resource budgets across execution layers.
"""

from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class ExecutionContext(BaseModel):
    """Explicit runtime context for an individual task or execution step."""

    task_id: str
    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    node_id: Optional[str] = None
    origin_device: str = "laptop-01"
    execution_device: str = "laptop-01"
    permissions: List[str] = Field(default_factory=list)
    priority: str = "normal"  # "critical", "high", "normal", "low", "background"

    # Resource constraints
    max_ram_mb: int = 4096
    max_vram_mb: int = 2048
    timeout_seconds: float = 60.0

    # Policy overrides
    network_allowed: bool = True
    gpu_allowed: bool = True
    requires_approval: bool = False

    metadata: Dict[str, Any] = Field(default_factory=dict)
