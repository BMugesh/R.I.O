"""R.I.O. Capability-Based Permission Engine.

Enforces least-privilege security. Every hardware/OS action received from R.I.O. Core
or external triggers must map to an explicitly enabled capability permission.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from runtime.device_manager import get_rio_config_dir

logger = logging.getLogger("rio.runtime.permissions")


class Capability:
    SCREEN_READ = "screen.read"
    SCREEN_RECORD = "screen.record"
    MOUSE_CONTROL = "mouse.control"
    KEYBOARD_CONTROL = "keyboard.control"
    APPLICATION_LAUNCH = "application.launch"
    APPLICATION_CLOSE = "application.close"
    BROWSER_CONTROL = "browser.control"
    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    MICROPHONE_READ = "microphone.read"
    CAMERA_READ = "camera.read"


DEFAULT_PERMISSIONS: Dict[str, bool] = {
    Capability.SCREEN_READ: True,
    Capability.SCREEN_RECORD: False,
    Capability.MOUSE_CONTROL: True,
    Capability.KEYBOARD_CONTROL: True,
    Capability.APPLICATION_LAUNCH: True,
    Capability.APPLICATION_CLOSE: True,
    Capability.BROWSER_CONTROL: True,
    Capability.FILESYSTEM_READ: True,
    Capability.FILESYSTEM_WRITE: False,
    Capability.MICROPHONE_READ: False,
    Capability.CAMERA_READ: False,
}

# Mapping from incoming action names to required capability
ACTION_CAPABILITY_MAP: Dict[str, str] = {
    # Screen
    "screenshot": Capability.SCREEN_READ,
    "screen_capture": Capability.SCREEN_READ,
    "screen.read": Capability.SCREEN_READ,
    "start_recording": Capability.SCREEN_RECORD,
    "screen.record": Capability.SCREEN_RECORD,
    # Mouse
    "mouse_click": Capability.MOUSE_CONTROL,
    "mouse_move": Capability.MOUSE_CONTROL,
    "double_click": Capability.MOUSE_CONTROL,
    "mouse.control": Capability.MOUSE_CONTROL,
    "locate_contact": Capability.MOUSE_CONTROL,
    # Keyboard
    "type_text": Capability.KEYBOARD_CONTROL,
    "keyboard_type": Capability.KEYBOARD_CONTROL,
    "hotkey": Capability.KEYBOARD_CONTROL,
    "send_message": Capability.KEYBOARD_CONTROL,
    "keyboard.control": Capability.KEYBOARD_CONTROL,
    # Applications
    "open_application": Capability.APPLICATION_LAUNCH,
    "launch_app": Capability.APPLICATION_LAUNCH,
    "application.launch": Capability.APPLICATION_LAUNCH,
    "close_application": Capability.APPLICATION_CLOSE,
    "application.close": Capability.APPLICATION_CLOSE,
    # Browser
    "browser_navigate": Capability.BROWSER_CONTROL,
    "browser.control": Capability.BROWSER_CONTROL,
    # Filesystem
    "read_file": Capability.FILESYSTEM_READ,
    "filesystem.read": Capability.FILESYSTEM_READ,
    "write_file": Capability.FILESYSTEM_WRITE,
    "delete_file": Capability.FILESYSTEM_WRITE,
    "filesystem.write": Capability.FILESYSTEM_WRITE,
    # Media
    "capture_photo": Capability.CAMERA_READ,
    "camera.read": Capability.CAMERA_READ,
    "record_audio": Capability.MICROPHONE_READ,
    "microphone.read": Capability.MICROPHONE_READ,
    # Status / Verification (always allowed without hardware side-effects)
    "get_device_status": "status",
    "verify_file": "status",
    "verify_app_state": "status",
    "verify_chat_delivery": "status",
}


class PermissionManager:
    """Manages persistent capability permissions on the local device."""

    PERMISSIONS_FILE_NAME = "permissions.json"

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or get_rio_config_dir()
        self.permissions_path = self.config_dir / self.PERMISSIONS_FILE_NAME
        self._permissions: Dict[str, bool] = dict(DEFAULT_PERMISSIONS)
        self._load()

    def _load(self) -> None:
        """Load configured permissions from disk."""
        if self.permissions_path.is_file():
            try:
                with open(self.permissions_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        if k in self._permissions:
                            self._permissions[k] = bool(v)
            except Exception as e:
                logger.warning(f"Failed to load permissions ({e}), using default permissions.")
        else:
            self.save()

    def save(self) -> None:
        """Save permissions to disk."""
        try:
            with open(self.permissions_path, "w", encoding="utf-8") as f:
                json.dump(self._permissions, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save permissions to {self.permissions_path}: {e}")

    def is_permitted(self, capability: str) -> bool:
        """Check if a specific capability is explicitly permitted."""
        if capability == "status":
            return True
        return self._permissions.get(capability, False)

    def is_action_allowed(self, action: str) -> tuple[bool, Optional[str]]:
        """Validate whether an action string is permitted.
        
        Returns: (is_allowed, required_capability)
        """
        req_cap = ACTION_CAPABILITY_MAP.get(action.lower())
        if not req_cap:
            # Unmapped actions default to strict denial
            return False, f"unmapped_action:{action}"
        if req_cap == "status":
            return True, "status"
        return self.is_permitted(req_cap), req_cap

    def set_permission(self, capability: str, allowed: bool) -> None:
        """Update and persist a capability permission."""
        if capability in self._permissions:
            self._permissions[capability] = bool(allowed)
            self.save()
            logger.info(f"Permission updated: {capability} -> {allowed}")
        else:
            logger.warning(f"Unknown capability: {capability}")

    def get_all_permissions(self) -> Dict[str, bool]:
        """Return all defined capability permissions."""
        return dict(self._permissions)

    def get_active_capabilities(self) -> List[str]:
        """Return list of all currently enabled capabilities."""
        return [cap for cap, enabled in self._permissions.items() if enabled]
