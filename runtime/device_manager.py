"""R.I.O. Device Identity and Configuration Manager.

Maintains a stable, unique device ID and hardware profile across reboots and runtime sessions.
Persists configuration securely in the local user application data directory.
"""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import platform
import socket
from typing import Any, Dict, List, Optional
import uuid

logger = logging.getLogger("rio.runtime.device")


def get_rio_config_dir() -> Path:
    """Return the platform-appropriate R.I.O. configuration directory."""
    if platform.system() == "Windows":
        app_data = os.getenv("APPDATA") or os.path.expanduser(r"~\AppData\Roaming")
        config_dir = Path(app_data) / "RIO"
    else:
        config_dir = Path.home() / ".rio"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


class DeviceManager:
    """Manages persistent device identification and hardware profile."""

    CONFIG_FILE_NAME = "device_config.json"

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or get_rio_config_dir()
        self.config_path = self.config_dir / self.CONFIG_FILE_NAME
        self._data: Dict[str, Any] = {}
        self._load_or_initialize()

    def _load_or_initialize(self) -> None:
        """Load existing device configuration or initialize a new stable identity."""
        if self.config_path.is_file():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                if "device_id" in self._data:
                    logger.debug(f"Loaded existing device identity: {self._data['device_id']}")
                    return
            except Exception as e:
                logger.warning(f"Failed to read device config ({e}), initializing fresh configuration.")

        # Initialize fresh stable identity
        generated_id = f"device-{socket.gethostname().lower()}-{uuid.uuid4().hex[:8]}"
        device_name = socket.gethostname() or "Workstation"
        self._data = {
            "device_id": generated_id,
            "device_name": device_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "platform": platform.system().lower(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "runtime_version": "1.0.0",
        }
        self.save()
        logger.info(f"Generated new stable device identity: {generated_id}")

    def save(self) -> None:
        """Persist device configuration to disk."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save device config to {self.config_path}: {e}")

    @property
    def device_id(self) -> str:
        return self._data.get("device_id", "unknown-device")

    @property
    def device_name(self) -> str:
        return self._data.get("device_name", socket.gethostname())

    @property
    def runtime_version(self) -> str:
        return self._data.get("runtime_version", "1.0.0")

    def get_registration_payload(self, capabilities: List[str], permissions: List[str]) -> Dict[str, Any]:
        """Generate structured device registration payload for R.I.O. Core."""
        return {
            "type": "device_register",
            "device_id": self.device_id,
            "device_name": self.device_name,
            "platform": platform.system().lower(),
            "platform_version": f"{platform.system()} {platform.release()}",
            "architecture": platform.machine(),
            "runtime_version": self.runtime_version,
            "capabilities": capabilities,
            "permissions": permissions,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
