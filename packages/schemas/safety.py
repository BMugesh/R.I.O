"""Safety & Approval Schemas for R.I.O.

Defines the security clearance, risk classification, and human-in-the-loop approval gates.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field
from packages.schemas.agents import AgentRiskLevel


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class ApprovalRequest(BaseModel):
    """A human-in-the-loop approval request for risky operations."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    step_id: Optional[str] = None
    action_type: str
    target: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    description: str
    risk_level: AgentRiskLevel
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    decision_reason: Optional[str] = None
    timeout_seconds: float = 300.0


class ApprovalDecision(BaseModel):
    """User response to an approval request."""
    request_id: str
    decision: ApprovalStatus  # APPROVED or DENIED
    user_id: Optional[str] = None
    reason: Optional[str] = None


class SafetyPolicy(BaseModel):
    """System-wide safety policy."""
    auto_execute_max_risk: AgentRiskLevel = AgentRiskLevel.MEDIUM
    require_approval_threshold: AgentRiskLevel = AgentRiskLevel.HIGH
    blocked_commands: List[str] = Field(default_factory=lambda: [
        "rm -rf /", "mkfs", "dd if=", ":(){ :|:& };:", "chmod -R 777 /",
        "DROP DATABASE", "DELETE FROM users", "shutdown", "reboot"
    ])
    allowed_filesystem_roots: List[str] = Field(default_factory=lambda: ["./data", "./workspace", "./downloads"])
