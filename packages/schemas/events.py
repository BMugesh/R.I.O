"""Internal Strongly Typed Event System for R.I.O.

These events flow through the internal event bus to orchestrate agents, tools,
devices, verification, and telemetry. Internal events are NEVER automatically displayed
to the user unless in Developer/Debug mode.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, Field


class EventType(str, Enum):
    USER_MESSAGE = "user_message"
    ASSISTANT_MESSAGE = "assistant_message"
    TASK_CREATED = "task_created"
    TASK_PLANNED = "task_planned"
    AGENT_SELECTED = "agent_selected"
    MODEL_SELECTED = "model_selected"
    TOOL_REQUESTED = "tool_requested"
    TOOL_RESULT = "tool_result"
    DEVICE_COMMAND = "device_command"
    DEVICE_OBSERVATION = "device_observation"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_SUCCESS = "verification_success"
    VERIFICATION_FAILED = "verification_failed"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_RETRY = "task_retry"
    QUANTUM_JOB = "quantum_job"
    QUANTUM_RESULT = "quantum_result"


class RIOEvent(BaseModel):
    """Internal event envelope."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: EventType
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    task_id: Optional[str] = None
    step_id: Optional[str] = None
    trace_id: Optional[str] = None
    agent_id: Optional[str] = None
    model_id: Optional[str] = None
    device_id: Optional[str] = None
    tool_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
