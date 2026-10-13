"""Conversation Message Models for R.I.O. (Milestone 5.x)."""

from datetime import datetime, timezone
from enum import Enum
import time
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConversationMessage(BaseModel):
    """Single turn in a conversation."""
    role: MessageRole
    content: str
    timestamp: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)
