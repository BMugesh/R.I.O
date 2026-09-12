"""R.I.O. Android Device Identity Manager.

Maintains a persistent, unique mobile hardware identity across app restarts
and Android system reboots without harvesting sensitive hardware telemetry.
"""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

logger = logging.getLogger("rio.android.device")


class AndroidDeviceManager:
    """Manages persistent Android phone device identification and profile."""

    CONFIG_FILE_NAME = "android_device_config.json"

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or self._get_default_android_storage_dir()
        self.config_path = self.storage_dir / self.CONFIG_FILE_NAME
        self._data: Dict[str, Any] = {}
        self._load_or_initialize()

    def _get_default_android_storage_dir(self) -> Path:
        """Return app-private data directory on Android/desktop fallback."""
        if os.name == "nt":
            app_data = os.getenv("APPDATA") or os.path.expanduser(r"~\AppData\Roaming")
            p = Path(app_data) / "RIO" / "android"
        else:
            p = Path.home() / ".rio" / "android"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _load_or_initialize(self) -> None:
        """Load existing device configuration or initialize a new stable identity."""
        if self.config_path.is_file():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                if "device_id" in self._data:
                    logger.debug(f"Loaded existing Android device identity: {self._data['device_id']}")
                    return
            except Exception as e:
                logger.warning(f"Failed to load Android config ({e}), generating fresh identity.")

        # Generate stable app-scoped UUID identity
        stable_id = f"rio-phone-{uuid.uuid4().hex[:8]}"
        self._data = {
            "device_id": stable_id,
            "device_name": "Mugi Phone",
            "platform": "android",
            "platform_version": "Android 14 (API 34)",
            "model": "Pixel 8 Pro",
            "manufacturer": "Google",
            "architecture": "aarch64",
            "runtime_version": "0.2.1-dev",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.save()
        logger.info(f"Generated new Android device identity: {stable_id}")

    def save(self) -> None:
        """Persist Android device configuration to storage."""
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save Android device config: {e}")

    @property
    def device_id(self) -> str:
        return self._data.get("device_id", "rio-phone-default")

    @property
    def device_name(self) -> str:
        return self._data.get("device_name", "Android Device")

    @property
    def runtime_version(self) -> str:
        return self._data.get("runtime_version", "0.2.1-dev")

    @property
    def platform_version(self) -> str:
        return self._data.get("platform_version", "Android 14 (API 34)")

    def get_registration_payload(self, capabilities: List[str], permissions: List[str]) -> Dict[str, Any]:
        """Generate structured Android device registration payload for R.I.O. Core."""
        return {
            "type": "device_register",
            "device_id": self.device_id,
            "device_name": self.device_name,
            "platform": "android",
            "platform_version": self.platform_version,
            "architecture": self._data.get("architecture", "aarch64"),
            "runtime_version": self.runtime_version,
            "capabilities": capabilities,
            "permissions": permissions,
            "metadata": {
                "model": self._data.get("model", "Pixel 8 Pro"),
                "manufacturer": self._data.get("manufacturer", "Google"),
                "is_mobile": True,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
