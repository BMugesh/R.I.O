"""Universal Input Envelope for R.I.O.

Normalizes all incoming multimodal inputs before reaching the orchestration layer.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class InputType(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    VIDEO = "video"
    SCREEN = "screen"
    DOCUMENT = "document"
    SENSOR = "sensor"
    LOCATION = "location"
    EVENT = "event"
    DEVICE = "device"
    GESTURE = "gesture"
    TOOL_RESULT = "tool_result"
    MEMORY_CONTEXT = "memory_context"


from packages.schemas.devices import OriginContext


class InputMetadata(BaseModel):
    client_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    device_id: Optional[str] = None
    interface_type: Optional[str] = None
    origin_context: Optional[OriginContext] = None
    mime_type: Optional[str] = None
    file_name: Optional[str] = None
    file_size_bytes: Optional[int] = None
    language: Optional[str] = "en"
    coordinates: Optional[Dict[str, float]] = None  # For location / cursor coordinates
    device_type: Optional[str] = None
    custom: Dict[str, Any] = Field(default_factory=dict)



class RIOInput(BaseModel):
    """Universal Typed Input Envelope."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: InputType = InputType.TEXT
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "web_chat"  # e.g., 'web_chat', 'voice_stream', 'desktop_agent', 'mobile_app', 'webhook'
    payload: Any = None  # Text string, base64 audio/image, file bytes, json dict, etc.
    metadata: InputMetadata = Field(default_factory=InputMetadata)

    def get_text_content(self) -> str:
        """Extract primary text or string representation from payload."""
        if isinstance(self.payload, str):
            return self.payload
        if isinstance(self.payload, dict):
            for key in ("text", "query", "message", "content", "goal", "prompt"):
                if key in self.payload and self.payload[key] is not None:
                    return str(self.payload[key])
            return str(self.payload)
        return str(self.payload) if self.payload is not None else ""

