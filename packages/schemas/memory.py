"""Memory System Schemas for R.I.O.

Supports short-term, episodic, semantic (pgvector), and device state memory models.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    SHORT_TERM = "short_term"
    CONVERSATION = "conversation"
    TASK = "task"
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    DEVICE_STATE = "device_state"
    USER_PREFERENCE = "user_preference"


class MemoryItem(BaseModel):
    """An individual memory record."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    type: MemoryType = MemoryType.SEMANTIC
    content: str
    embedding: Optional[List[float]] = None
    importance: float = 0.5  # 0.0 to 1.0
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_accessed: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    access_count: int = 0
    ttl_seconds: Optional[int] = None


class MemoryQuery(BaseModel):
    """Query parameters for retrieving relevant memories."""
    text: str
    types: Optional[List[MemoryType]] = None
    limit: int = 5
    min_similarity: float = 0.6
    user_id: Optional[str] = None
    tags: Optional[List[str]] = None


class MemoryPolicy(BaseModel):
    """Retention, privacy, and auto-summarization policy."""
    auto_prune_low_importance: bool = True
    min_importance_threshold: float = 0.2
    max_short_term_turns: int = 20
    semantic_decay_factor: float = 0.95
