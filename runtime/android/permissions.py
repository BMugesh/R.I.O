"""R.I.O. Android Capability & Dual-Permission Engine.

Enforces least-privilege security on mobile devices.
Core Principle: R.I.O. Permission + Android OS Permission = Capability Available.
If either layer denies access, the operation is immediately rejected.
"""

from enum import Enum
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("rio.android.permissions")


class AndroidCapability(str, Enum):
    SCREEN_READ = "screen.read"
    TOUCH_CONTROL = "touch.control"
    APPLICATION_LAUNCH = "application.launch"
    APPLICATION_CLOSE = "application.close"
    CAMERA_READ = "camera.read"
    MICROPHONE_READ = "microphone.read"
    NOTIFICATIONS_READ = "notifications.read"
    NOTIFICATIONS_SEND = "notifications.send"
    LOCATION_READ = "location.read"
    SENSORS_READ = "sensors.read"
    FILESYSTEM_READ = "filesystem.read"


# Default R.I.O. permission policy on Android
DEFAULT_RIO_PERMISSIONS: Dict[str, bool] = {
    AndroidCapability.SCREEN_READ.value: True,
    AndroidCapability.TOUCH_CONTROL.value: True,
    AndroidCapability.APPLICATION_LAUNCH.value: True,
    AndroidCapability.APPLICATION_CLOSE.value: True,
    AndroidCapability.CAMERA_READ.value: True,
    AndroidCapability.MICROPHONE_READ.value: True,
    AndroidCapability.NOTIFICATIONS_READ.value: True,
    AndroidCapability.NOTIFICATIONS_SEND.value: True,
    AndroidCapability.LOCATION_READ.value: False,
    AndroidCapability.SENSORS_READ.value: True,
    AndroidCapability.FILESYSTEM_READ.value: False,
}

# Android OS Runtime Permission Mapping
ANDROID_OS_PERMISSION_MAP: Dict[str, str] = {
    AndroidCapability.SCREEN_READ.value: "android.permission.MEDIA_PROJECTION",
    AndroidCapability.TOUCH_CONTROL.value: "android.permission.BIND_ACCESSIBILITY_SERVICE",
    AndroidCapability.APPLICATION_LAUNCH.value: "android.permission.QUERY_ALL_PACKAGES",
    AndroidCapability.CAMERA_READ.value: "android.permission.CAMERA",
    AndroidCapability.MICROPHONE_READ.value: "android.permission.RECORD_AUDIO",
    AndroidCapability.NOTIFICATIONS_READ.value: "android.permission.BIND_NOTIFICATION_LISTENER_SERVICE",
    AndroidCapability.NOTIFICATIONS_SEND.value: "android.permission.POST_NOTIFICATIONS",
    AndroidCapability.LOCATION_READ.value: "android.permission.ACCESS_FINE_LOCATION",
    AndroidCapability.SENSORS_READ.value: "android.permission.BODY_SENSORS",
    AndroidCapability.FILESYSTEM_READ.value: "android.permission.READ_EXTERNAL_STORAGE",
}

ACTION_TO_ANDROID_CAPABILITY: Dict[str, str] = {
    "open_mobile_app": AndroidCapability.APPLICATION_LAUNCH.value,
    "launch_app": AndroidCapability.APPLICATION_LAUNCH.value,
    "application.launch": AndroidCapability.APPLICATION_LAUNCH.value,
    "android.launch_app": AndroidCapability.APPLICATION_LAUNCH.value,
    "touch.tap": AndroidCapability.TOUCH_CONTROL.value,
    "touch_tap": AndroidCapability.TOUCH_CONTROL.value,
    "touch.swipe": AndroidCapability.TOUCH_CONTROL.value,
    "touch_swipe": AndroidCapability.TOUCH_CONTROL.value,
    "screen.capture": AndroidCapability.SCREEN_READ.value,
    "screenshot": AndroidCapability.SCREEN_READ.value,
    "android.screen.capture": AndroidCapability.SCREEN_READ.value,
    "capture_photo": AndroidCapability.CAMERA_READ.value,
    "camera.capture": AndroidCapability.CAMERA_READ.value,
    "android.camera.capture": AndroidCapability.CAMERA_READ.value,
    "record_audio": AndroidCapability.MICROPHONE_READ.value,
    "microphone.capture": AndroidCapability.MICROPHONE_READ.value,
    "android.microphone.capture": AndroidCapability.MICROPHONE_READ.value,
    "send_notification": AndroidCapability.NOTIFICATIONS_SEND.value,
    "notification.send": AndroidCapability.NOTIFICATIONS_SEND.value,
    "read_notifications": AndroidCapability.NOTIFICATIONS_READ.value,
    "notification.read": AndroidCapability.NOTIFICATIONS_READ.value,
    "get_location": AndroidCapability.LOCATION_READ.value,
    "location.read": AndroidCapability.LOCATION_READ.value,
    "get_sensors": AndroidCapability.SENSORS_READ.value,
    "sensors.read": AndroidCapability.SENSORS_READ.value,
    "get_device_status": "status",
}


class AndroidPermissionManager:
    """Manages dual-layer capability permission authorization on Android devices."""

    PERMISSIONS_FILE_NAME = "android_permissions.json"

    def __init__(self, storage_dir: Optional[Path] = None):
        if storage_dir:
            self.storage_dir = storage_dir
        elif os.name == "nt":
            app_data = os.getenv("APPDATA") or os.path.expanduser(r"~\AppData\Roaming")
            self.storage_dir = Path(app_data) / "RIO" / "android"
        else:
            self.storage_dir = Path.home() / ".rio" / "android"

        self.permissions_path = self.storage_dir / self.PERMISSIONS_FILE_NAME
        self._rio_permissions: Dict[str, bool] = dict(DEFAULT_RIO_PERMISSIONS)
        self._os_granted_permissions: Dict[str, bool] = {
            os_perm: True for os_perm in ANDROID_OS_PERMISSION_MAP.values()
        }
        self._load()

    def _load(self) -> None:
        """Load configured R.I.O. permissions from disk."""
        if self.permissions_path.is_file():
            try:
                with open(self.permissions_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    rio_data = data.get("rio_permissions", {})
                    for k, v in rio_data.items():
                        if k in self._rio_permissions:
                            self._rio_permissions[k] = bool(v)
                    os_data = data.get("os_permissions", {})
                    for k, v in os_data.items():
                        self._os_granted_permissions[k] = bool(v)
            except Exception as e:
                logger.warning(f"Failed to load Android permissions ({e}), using defaults.")
        else:
            self.save()

    def save(self) -> None:
        """Persist Android permissions state."""
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            with open(self.permissions_path, "w", encoding="utf-8") as f:
                json.dump({
                    "rio_permissions": self._rio_permissions,
                    "os_permissions": self._os_granted_permissions,
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save Android permissions: {e}")

    def is_rio_permitted(self, capability: str) -> bool:
        """Check R.I.O. layer permission."""
        return self._rio_permissions.get(capability, False)

    def is_os_permission_granted(self, os_permission: str) -> bool:
        """Check Android OS layer permission."""
        return self._os_granted_permissions.get(os_permission, False)

    def is_capability_available(self, capability: str) -> Tuple[bool, Optional[str]]:
        """Evaluate dual-layer permission: R.I.O. + Android OS.
        
        Returns: (is_available, denial_reason)
        """
        if capability == "status":
            return True, None

        # Layer 1: R.I.O. Permission Check
        if not self.is_rio_permitted(capability):
            return False, f"Denied by R.I.O. capability policy: '{capability}' is disabled."

        # Layer 2: Android OS Permission Check
        required_os_perm = ANDROID_OS_PERMISSION_MAP.get(capability)
        if required_os_perm and not self.is_os_permission_granted(required_os_perm):
            return False, f"Denied by Android OS: Missing required system permission '{required_os_perm}'."

        return True, None

    def is_action_allowed(self, action: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Check if action is permitted by mapping to capability and checking dual layers.
        
        Returns: (is_allowed, capability, denial_reason)
        """
        act_clean = action.lower()
        cap = ACTION_TO_ANDROID_CAPABILITY.get(act_clean)
        if not cap:
            return False, None, f"Unmapped Android action: '{action}'."

        if cap == "status":
            return True, "status", None

        available, reason = self.is_capability_available(cap)
        return available, cap, reason

    def set_rio_permission(self, capability: str, allowed: bool) -> None:
        """Update R.I.O. permission boundary."""
        if capability in self._rio_permissions:
            self._rio_permissions[capability] = bool(allowed)
            self.save()

    def set_os_permission_grant(self, os_permission: str, granted: bool) -> None:
        """Update Android OS granted permission state (simulated or via system callback)."""
        self._os_granted_permissions[os_permission] = bool(granted)
        self.save()

    def get_active_capabilities(self) -> List[str]:
        """Return list of all currently available capabilities satisfying both R.I.O. and OS layers."""
        active = []
        for cap in self._rio_permissions:
            avail, _ = self.is_capability_available(cap)
            if avail:
                active.append(cap)
        return active

    def get_all_permissions(self) -> Dict[str, bool]:
        """Return R.I.O. permissions dictionary."""
        return dict(self._rio_permissions)
