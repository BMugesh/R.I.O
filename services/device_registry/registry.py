"""Device Registry for R.I.O. Core.

Manages persistent hardware identities, active connection states, capability advertisements,
and permission profiles across all connected laptops, phones, and servers.
"""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from packages.schemas.devices import (
    Device,
    DeviceCapability,
    DeviceStatus,
    DeviceType,
)

logger = logging.getLogger("rio.device_registry")


class DeviceRegistry:
    """Central Device Registry for R.I.O. Operating System."""

    PERSISTENCE_FILE = "registered_devices.json"

    def __init__(self, persistence_dir: Optional[Path] = None, seed_defaults: bool = True):
        self.persistence_dir = persistence_dir or self._get_default_storage_dir()
        self.persistence_path = self.persistence_dir / self.PERSISTENCE_FILE
        self._devices: Dict[str, Device] = {}
        self._load()
        if seed_defaults and not self._devices:
            self._seed_default_devices()

    def _get_default_storage_dir(self) -> Path:
        """Return the default configuration storage directory."""
        if os.name == "nt":
            app_data = os.getenv("APPDATA") or os.path.expanduser(r"~\AppData\Roaming")
            p = Path(app_data) / "RIO"
        else:
            p = Path.home() / ".rio"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _seed_default_devices(self) -> None:
        """Seed default device profiles if registry is freshly initialized."""
        laptop = Device(
            device_id="laptop-01",
            name="Primary Workstation",
            device_name="Primary Workstation",
            type=DeviceType.LAPTOP,
            platform="windows",
            status=DeviceStatus.ONLINE,
            capabilities=[
                DeviceCapability.SCREEN_READ,
                DeviceCapability.MOUSE_CONTROL,
                DeviceCapability.KEYBOARD_CONTROL,
                DeviceCapability.APPLICATION_LAUNCH,
                DeviceCapability.APPLICATION_CLOSE,
                DeviceCapability.BROWSER_CONTROL,
                DeviceCapability.FILESYSTEM_READ,
            ],
            permissions=["all"],
            os_info="Windows 11 Pro",
            last_seen=datetime.now(timezone.utc).isoformat(),
            metadata={"hostname": "Mugi-Laptop", "is_primary": True},
        )
        phone = Device(
            device_id="android-01",
            name="Mugi Phone",
            device_name="Mugi Phone",
            type=DeviceType.ANDROID,
            platform="android",
            status=DeviceStatus.ONLINE,
            capabilities=[
                DeviceCapability.CAMERA_READ,
                DeviceCapability.MICROPHONE_READ,
                DeviceCapability.NOTIFICATIONS_READ,
                DeviceCapability.NOTIFICATIONS_SEND,
                DeviceCapability.LOCATION_READ,
                DeviceCapability.SENSORS_READ,
                DeviceCapability.APPLICATION_LAUNCH,
                DeviceCapability.TOUCH_CONTROL,
                DeviceCapability.SCREEN_READ,
            ],
            permissions=["read_notifications", "camera", "microphone", "touch", "app_launch"],
            os_info="Android 14 (API 34)",
            last_seen=datetime.now(timezone.utc).isoformat(),
            metadata={"model": "Pixel 8 Pro", "is_mobile": True},
        )
        self._devices[laptop.device_id] = laptop
        self._devices[phone.device_id] = phone
        self.save()

    def _load(self) -> None:
        """Load registered devices from disk."""
        if self.persistence_path.is_file():
            try:
                with open(self.persistence_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        dev = Device(**item)
                        # Ensure mobile devices have standard mobile capabilities
                        if dev.platform == "android" or dev.type == DeviceType.ANDROID:
                            for cap in (DeviceCapability.APPLICATION_LAUNCH, DeviceCapability.TOUCH_CONTROL, DeviceCapability.SCREEN_READ, DeviceCapability.CAMERA_READ, DeviceCapability.MICROPHONE_READ):
                                if cap not in dev.capabilities and cap.value not in dev.capabilities:
                                    dev.capabilities.append(cap)
                        elif dev.platform == "windows" or dev.type in (DeviceType.LAPTOP, DeviceType.DESKTOP):
                            for cap in (DeviceCapability.APPLICATION_LAUNCH, DeviceCapability.APPLICATION_CLOSE, DeviceCapability.SCREEN_READ, DeviceCapability.MOUSE_CONTROL, DeviceCapability.KEYBOARD_CONTROL, DeviceCapability.BROWSER_CONTROL):
                                if cap not in dev.capabilities and cap.value not in dev.capabilities:
                                    dev.capabilities.append(cap)
                        self._devices[dev.device_id] = dev
                logger.debug(f"Loaded {len(self._devices)} devices from registry persistence.")
            except Exception as e:
                logger.warning(f"Failed to load device registry ({e}), starting with empty in-memory store.")

    def save(self) -> None:
        """Persist device registry to disk."""
        try:
            self.persistence_dir.mkdir(parents=True, exist_ok=True)
            with open(self.persistence_path, "w", encoding="utf-8") as f:
                json_data = [d.model_dump() for d in self._devices.values()]
                json.dump(json_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save device registry to {self.persistence_path}: {e}")

    def register_device(self, device: Device) -> Device:
        """Register or update a hardware device."""
        device.last_seen = datetime.now(timezone.utc).isoformat()
        device.status = DeviceStatus.ONLINE
        device.connection_state = "online"
        self._devices[device.device_id] = device
        self.save()
        logger.info(f"Registered device: {device.device_id} ({device.name}) - Platform: {device.platform}")
        return device

    def unregister_device(self, device_id: str) -> bool:
        """Remove a device from registry."""
        if device_id in self._devices:
            del self._devices[device_id]
            self.save()
            logger.info(f"Unregistered device: {device_id}")
            return True
        return False

    def record_heartbeat(self, device_id: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Update last_seen and telemetry on heartbeat."""
        dev = self.get_device(device_id)
        if dev:
            dev.last_seen = datetime.now(timezone.utc).isoformat()
            dev.status = DeviceStatus.ONLINE
            dev.connection_state = "online"
            if metadata:
                dev.metadata.update(metadata)
            return True
        return False

    def disconnect_device(self, device_id: str) -> bool:
        """Mark device connection status as offline."""
        dev = self.get_device(device_id)
        if dev:
            dev.status = DeviceStatus.OFFLINE
            dev.connection_state = "offline"
            self.save()
            logger.info(f"Device disconnected: {device_id}")
            return True
        return False

    def reconnect_device(self, device_id: str) -> bool:
        """Mark device connection status as online."""
        dev = self.get_device(device_id)
        if dev:
            dev.status = DeviceStatus.ONLINE
            dev.connection_state = "online"
            dev.last_seen = datetime.now(timezone.utc).isoformat()
            self.save()
            return True
        return False

    def get_device(self, device_id: str) -> Optional[Device]:
        """Lookup a device by device_id or alias."""
        if not device_id:
            return None
        dev = self._devices.get(device_id)
        if dev:
            return dev
        dev_lower = device_id.lower().strip()
        if dev_lower in ("phone-01", "phone", "android-01", "mobile-01", "pixel"):
            for d in self._devices.values():
                if d.platform == "android" or d.type == DeviceType.ANDROID:
                    return d
        if dev_lower in ("laptop-01", "laptop", "desktop-01", "desktop", "workstation-01", "pc"):
            for d in self._devices.values():
                if d.platform in ("windows", "desktop") or d.type in (DeviceType.LAPTOP, DeviceType.DESKTOP):
                    return d
        return self.get_device_by_name(device_id)


    def get_device_by_name(self, name: str) -> Optional[Device]:
        """Lookup a device by name or alias (case-insensitive substring match)."""
        name_lower = name.lower().strip()
        # Direct exact match
        for d in self._devices.values():
            if d.device_id.lower() == name_lower or (d.name and d.name.lower() == name_lower):
                return d
        # Substring match
        for d in self._devices.values():
            if (d.name and name_lower in d.name.lower()) or (name_lower in d.device_id.lower()):
                return d
        return None

    def list_devices(self, filter_status: Optional[DeviceStatus] = None) -> List[Device]:
        """Return list of all registered devices, optionally filtered by status."""
        if filter_status is not None:
            return [d for d in self._devices.values() if d.status == filter_status]
        return list(self._devices.values())

    def get_devices_with_capability(self, capability: str) -> List[Device]:
        """Find all registered devices advertising a specific capability."""
        cap_clean = capability.lower().replace("_", ".")
        matches = []
        for d in self._devices.values():
            for c in d.capabilities:
                c_str = str(c.value if hasattr(c, "value") else c).lower().replace("_", ".")
                if c_str == cap_clean or cap_clean in c_str:
                    matches.append(d)
                    break
        return matches

    def get_devices_by_platform(self, platform_name: str) -> List[Device]:
        """Find all registered devices matching a platform string (e.g. 'windows', 'android')."""
        plat_lower = platform_name.lower().strip()
        return [d for d in self._devices.values() if plat_lower in (d.platform or "").lower() or plat_lower in d.type.value.lower()]
