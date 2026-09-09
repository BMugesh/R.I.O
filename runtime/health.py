"""R.I.O. Runtime Health and Telemetry Tracker.

Tracks local daemon uptime, connection state, heartbeat intervals, command metrics,
and error telemetry. Persists live state to disk for instant cross-process CLI inspection.
"""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, Optional
from runtime.device_manager import get_rio_config_dir

logger = logging.getLogger("rio.runtime.health")


class RuntimeHealth:
    """Tracks and persists runtime operational health metrics."""

    HEALTH_FILE_NAME = "runtime_health.json"

    def __init__(self, device_id: str = "unknown", device_name: str = "Workstation", config_dir: Optional[Path] = None):
        self.config_dir = config_dir or get_rio_config_dir()
        self.health_path = self.config_dir / self.HEALTH_FILE_NAME
        self.device_id = device_id
        self.device_name = device_name
        self.start_time = time.time()
        self.connection_status = "offline"  # 'online', 'connecting', 'offline', 'error'
        self.core_url = ""
        self.last_heartbeat: Optional[str] = None
        self.last_command: Optional[str] = None
        self.last_command_action: Optional[str] = None
        self.last_successful_task: Optional[str] = None
        self.total_commands = 0
        self.error_count = 0
        self.reconnect_count = 0
        self.active_capabilities_count = 0
        self.pid = os.getpid()
        self.save()

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.start_time

    @property
    def uptime_formatted(self) -> str:
        seconds = int(self.uptime_seconds)
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        return f"{secs}s"

    def set_connection_status(self, status: str, core_url: Optional[str] = None) -> None:
        self.connection_status = status
        if core_url:
            self.core_url = core_url
        self.save()

    def record_heartbeat(self) -> None:
        self.last_heartbeat = datetime.now(timezone.utc).isoformat()
        self.save()

    def record_reconnect_attempt(self) -> None:
        self.reconnect_count += 1
        self.save()

    def record_command(self, action: str, success: bool = True) -> None:
        self.total_commands += 1
        now_iso = datetime.now(timezone.utc).isoformat()
        self.last_command = now_iso
        self.last_command_action = action
        if success:
            self.last_successful_task = now_iso
        else:
            self.error_count += 1
        self.save()

    def record_error(self, err_msg: Optional[str] = None) -> None:
        self.error_count += 1
        self.save()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pid": self.pid,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "status": self.connection_status.upper(),
            "core_url": self.core_url,
            "uptime": self.uptime_formatted,
            "uptime_seconds": self.uptime_seconds,
            "start_time": datetime.fromtimestamp(self.start_time, timezone.utc).isoformat(),
            "last_heartbeat": self.last_heartbeat or "None",
            "last_command": self.last_command or "None",
            "last_command_action": self.last_command_action or "None",
            "last_successful_task": self.last_successful_task or "None",
            "total_commands": self.total_commands,
            "error_count": self.error_count,
            "reconnect_count": self.reconnect_count,
            "capabilities_count": self.active_capabilities_count,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    def save(self) -> None:
        """Persist health metrics to disk."""
        try:
            with open(self.health_path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2)
        except Exception as e:
            logger.debug(f"Failed to persist health metrics: {e}")

    @classmethod
    def read_persisted_health(cls, config_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
        """Read persisted health snapshot from disk (used by CLI or external observers)."""
        c_dir = config_dir or get_rio_config_dir()
        h_path = c_dir / cls.HEALTH_FILE_NAME
        if h_path.is_file():
            try:
                with open(h_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data
            except Exception:
                return None
        return None
