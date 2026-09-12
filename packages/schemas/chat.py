"""Chat & User Interaction Schemas for R.I.O.

Defines external user request/response envelopes, streaming chunks,
and optional developer debug trace models.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field
from packages.schemas.devices import OriginContext
from packages.schemas.input import InputType
from packages.schemas.tasks import TaskPlan, TaskStep
from packages.schemas.safety import ApprovalRequest


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    role: MessageRole
    content: str
    input_type: InputType = InputType.TEXT
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ChatRequest(BaseModel):
    """User request sent to /api/v1/chat or WebSocket."""
    message: str
    session_id: Optional[str] = Field(default=None, alias="sessionId")
    user_id: Optional[str] = Field(default="default_user", alias="userId")
    input_type: InputType = Field(default=InputType.TEXT, alias="inputType")
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    device_id: Optional[str] = Field(default=None, alias="deviceId")
    origin_device_id: Optional[str] = Field(default=None, alias="originDeviceId")
    interface_type: Optional[str] = Field(default=None, alias="interfaceType")
    origin_context: Optional[OriginContext] = Field(default=None, alias="originContext")
    developer_mode: bool = Field(default=False, alias="developerMode")

    model_config = {"populate_by_name": True, "extra": "ignore"}


class DeveloperTrace(BaseModel):
    """Developer debug information. ONLY populated if requested explicitly."""
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    model_id: Optional[str] = None
    origin_device_id: Optional[str] = None
    execution_device_id: Optional[str] = None
    resolution_reason: Optional[str] = None
    explicit_override: bool = False
    plan: Optional[TaskPlan] = None
    steps: List[TaskStep] = Field(default_factory=list)
    events: List[Dict[str, Any]] = Field(default_factory=list)
    verification_summary: Optional[Dict[str, Any]] = None
    compute_trace: Optional[Dict[str, Any]] = None
    latency_ms: float = 0.0



class ChatResponse(BaseModel):
    """External response sent to the user."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    reply: str
    task_id: Optional[str] = None
    status: str = "completed"  # 'completed', 'waiting_approval', 'executing', 'failed'
    pending_approval: Optional[ApprovalRequest] = None
    developer_trace: Optional[DeveloperTrace] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ChatStreamChunk(BaseModel):
    """Real-time streaming chunk for WebSockets."""
    chunk_type: str  # 'token', 'status_update', 'approval_required', 'done', 'error'
    content: Optional[str] = None
    task_status: Optional[str] = None
    approval: Optional[ApprovalRequest] = None
    developer_trace: Optional[DeveloperTrace] = None
