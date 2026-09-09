"""Device Registry and Control Schemas for R.I.O.

Defines schemas for Desktop and Mobile (Android) agents and controlled hardware interaction.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class DeviceType(str, Enum):
    LAPTOP = "laptop"
    DESKTOP = "desktop"
    ANDROID = "android"
    IOS = "ios"
    SERVER = "server"
    CUSTOM = "custom"


class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"


class DeviceCapability(str, Enum):
    SCREEN_CAPTURE = "screen_capture"
    SCREEN_RECORDING = "screen_recording"
    MOUSE_CONTROL = "mouse_control"
    KEYBOARD_CONTROL = "keyboard_control"
    APP_MANAGEMENT = "app_management"
    BROWSER_CONTROL = "browser_control"
    FILESYSTEM = "filesystem"
    CAMERA = "camera"
    MICROPHONE = "microphone"
    NOTIFICATIONS = "notifications"
    LOCATION = "location"
    SENSORS = "sensors"


class Device(BaseModel):
    """A registered hardware device."""
    device_id: str
    name: str
    type: DeviceType = DeviceType.LAPTOP
    status: DeviceStatus = DeviceStatus.OFFLINE
    capabilities: List[DeviceCapability] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    ip_address: Optional[str] = None
    os_info: Optional[str] = None
    last_seen: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DeviceCommand(BaseModel):
    """Command sent from R.I.O. Core to a local Device Agent."""
    command_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str
    action: str  # e.g., 'screenshot', 'mouse_click', 'type_text', 'open_app', 'read_file'
    parameters: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = 30.0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DeviceObservation(BaseModel):
    """Observation returned by a Device Agent."""
    command_id: Optional[str] = None
    device_id: str
    success: bool = True
    action: str
    data: Any = None  # Base64 screenshot, active window title, file content, coordinates, etc.
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
