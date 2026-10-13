"""Task & Plan Graph Schemas for R.I.O.

Defines the Directed Acyclic Graph (DAG) task execution models, steps,
dependencies, retry policies, and verification strategies.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field
from packages.schemas.agents import Action, Evidence, AgentRiskLevel


class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    VERIFYING = "verifying"


class VerificationStrategy(BaseModel):
    """Specification of how to verify that a step succeeded."""
    strategy_type: str = "assertion"  # 'dom_query', 'file_check', 'window_check', 'api_status', 'text_match', 'screenshot_match'
    expected_state: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = 10.0
    retry_count: int = 2
    is_mandatory: bool = True


class TaskStep(BaseModel):
    """A discrete step in a task execution graph."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: Optional[str] = None
    name: str
    description: str = ""
    agent_id: str
    action: Action
    dependencies: List[str] = Field(default_factory=list)  # IDs of predecessor steps
    status: StepStatus = StepStatus.PENDING
    risk_level: AgentRiskLevel = AgentRiskLevel.LOW
    requires_approval: bool = False
    verification_strategy: Optional[VerificationStrategy] = None
    observation: Optional[Dict[str, Any]] = None
    evidence: List[Evidence] = Field(default_factory=list)
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    parallelizable: bool = True
    estimated_duration_ms: Optional[int] = None
    estimated_memory_mb: Optional[int] = None
    estimated_vram_mb: Optional[int] = None
    verification_level: Optional[str] = None
    priority: str = "normal"
    is_idempotent: bool = True


class TaskPlan(BaseModel):
    """A full Directed Acyclic Graph (DAG) plan of steps."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal: str
    steps: List[TaskStep] = Field(default_factory=list)
    estimated_duration_seconds: float = 0.0
    is_approved: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    analysis: Optional[Dict[str, Any]] = None
    execution_stages: List[List[str]] = Field(default_factory=list)
    max_parallelism: int = 1


class AutonomyBudget(BaseModel):
    """Execution constraints and boundaries to prevent infinite autonomy loops."""
    max_runtime_seconds: float = 120.0
    max_total_steps: int = 20
    max_replans: int = 2
    max_retries_per_step: int = 2


class Task(BaseModel):
    """High-level task representation."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    goal: str
    status: TaskStatus = TaskStatus.PENDING
    plan: Optional[TaskPlan] = None
    risk_level: AgentRiskLevel = AgentRiskLevel.LOW
    budget: Optional[AutonomyBudget] = Field(default_factory=AutonomyBudget)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    error: Optional[str] = None
    final_response: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
