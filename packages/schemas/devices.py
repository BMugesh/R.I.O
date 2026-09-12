"""Device Registry and Control Schemas for R.I.O.

Defines schemas for Desktop (Windows/Linux/macOS) and Mobile (Android/iOS) devices,
strongly typed device actions, capability permissions, and structured observations.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import uuid
from pydantic import BaseModel, Field


class DeviceType(str, Enum):
    LAPTOP = "laptop"
    DESKTOP = "desktop"
    ANDROID = "android"
    IOS = "ios"
    SERVER = "server"
    CUSTOM = "custom"


class InterfaceType(str, Enum):
    """Origin interface from which a user command or interaction originates."""
    WEB = "web"
    DESKTOP = "desktop"
    ANDROID = "android"
    IOS = "ios"
    CLI = "cli"
    API = "api"
    VOICE = "voice"


class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    REGISTERED = "registered"
    RECONNECTING = "reconnecting"
    STOPPED = "stopped"


class DeviceCapability(str, Enum):
    # Standard dot-notated capabilities
    SCREEN_READ = "screen.read"
    SCREEN_RECORD = "screen.record"
    MOUSE_CONTROL = "mouse.control"
    KEYBOARD_CONTROL = "keyboard.control"
    TOUCH_CONTROL = "touch.control"
    APPLICATION_LAUNCH = "application.launch"
    APPLICATION_CLOSE = "application.close"
    BROWSER_CONTROL = "browser.control"
    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    CAMERA_READ = "camera.read"
    MICROPHONE_READ = "microphone.read"
    NOTIFICATIONS_READ = "notifications.read"
    NOTIFICATIONS_SEND = "notifications.send"
    LOCATION_READ = "location.read"
    SENSORS_READ = "sensors.read"

    # Legacy snake_case aliases for backward compatibility
    SCREEN_CAPTURE = "screen_capture"
    SCREEN_RECORDING = "screen_recording"
    APP_MANAGEMENT = "app_management"
    FILESYSTEM = "filesystem"
    CAMERA = "camera"
    MICROPHONE = "microphone"
    NOTIFICATIONS = "notifications"
    LOCATION = "location"
    SENSORS = "sensors"


class OriginContext(BaseModel):
    """Context identifying where and how a user command originated."""
    session_id: str = "default_session"
    interface_type: Union[InterfaceType, str] = InterfaceType.CLI
    origin_device_id: Optional[str] = None
    origin_device_type: Optional[Union[DeviceType, str]] = None
    origin_platform: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Device(BaseModel):
    """A registered hardware device in the R.I.O. ecosystem."""
    device_id: str
    name: str
    device_name: Optional[str] = None
    platform: str = "windows"
    runtime_version: str = "0.2.1-dev"
    type: DeviceType = DeviceType.LAPTOP
    status: DeviceStatus = DeviceStatus.OFFLINE
    connection_state: Optional[str] = None
    capabilities: List[Union[DeviceCapability, str]] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    ip_address: Optional[str] = None
    os_info: Optional[str] = None
    last_seen: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.device_name and self.name:
            self.device_name = self.name
        elif not self.name and self.device_name:
            self.name = self.device_name
        if not self.connection_state and self.status:
            self.connection_state = self.status.value


class DeviceAction(BaseModel):
    """Strongly typed action dispatched to a target device runtime."""
    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str
    capability: str
    action_type: str  # e.g., 'application.launch', 'screen.capture', 'touch.tap', 'mouse.click'
    target: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    requested_by: str = "rio_core"
    timeout_seconds: float = 30.0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DeviceCommand(BaseModel):
    """Command sent from R.I.O. Core to a local Device Agent."""
    command_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str
    action: str  # e.g., 'screenshot', 'mouse_click', 'type_text', 'open_app', 'read_file'
    parameters: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = 30.0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DeviceObservation(BaseModel):
    """Structured observation returned by a Device Agent."""
    observation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    command_id: Optional[str] = None
    action_id: Optional[str] = None
    device_id: str
    observation_type: Optional[str] = None
    status: str = "verified"  # "verified", "uncertain", "failed", "rejected"
    success: bool = True
    action: str = ""
    data: Any = None  # Process info, window handle/title, screenshot path, coordinates, etc.
    evidence: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DeviceResolution(BaseModel):
    """Result of resolving target execution device for an action or intent."""
    origin_device_id: Optional[str] = None
    execution_device_id: Optional[str] = None
    target_device: Optional[Device] = None
    capability: Optional[str] = None
    reason: str = "default"
    explicit_override: bool = False
    is_ambiguous: bool = False
    ambiguity_message: Optional[str] = None
    error: Optional[str] = None

