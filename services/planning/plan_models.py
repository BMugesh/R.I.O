"""Task Planning & Graph Models for R.I.O. (Milestone 5).

Defines structured task analysis, validation results, and execution stage models.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TaskAnalysis(BaseModel):
    """Deep structural and resource analysis of a user task."""

    task_id: str
    goal: str
    complexity: str = "medium"  # "low", "medium", "high", "extreme"
    risk_level: str = "low"  # "low", "medium", "high", "critical"
    required_capabilities: List[str] = Field(default_factory=list)

    estimated_duration_ms: Optional[int] = None
    estimated_memory_mb: Optional[int] = None
    estimated_vram_mb: Optional[int] = None

    requires_network: bool = False
    requires_gpu: bool = False
    requires_device: bool = False

    reversible: bool = True
    requires_approval: bool = False
    verification_level: str = "standard"  # "none", "basic", "standard", "strict", "critical"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PlanValidationResult(BaseModel):
    """Result of validating a task execution plan prior to execution."""

    is_valid: bool = True
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class PlanOptimizationSummary(BaseModel):
    """Optimization summary grouping steps into concurrent execution stages."""

    stages: List[List[str]] = Field(default_factory=list)
    max_parallelism: int = 1
    critical_path: List[str] = Field(default_factory=list)
    estimated_total_duration_ms: int = 0
