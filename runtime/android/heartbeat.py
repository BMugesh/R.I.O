"""R.I.O. Android Heartbeat and Telemetry Reporter.

Emits periodic health signals, battery status, active capabilities,
and uptime to R.I.O. Core without collecting invasive personal telemetry.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("rio.android.heartbeat")


class AndroidHeartbeatManager:
    """Manages periodic heartbeat and telemetry broadcast for Android runtime."""

    def __init__(
        self,
        device_id: str,
        send_fn: Callable[[str], Any],
        interval_seconds: float = 20.0,
        runtime_version: str = "0.2.1-dev",
    ):
        self.device_id = device_id
        self.send_fn = send_fn
        self.interval_seconds = interval_seconds
        self.runtime_version = runtime_version

        self.start_time = time.time()
        self.total_commands = 0
        self.error_count = 0
        self.last_command: Optional[str] = None
        self.battery_level: float = 85.0
        self.is_charging: bool = False

        self._running = False
        self._task: Optional[asyncio.Task] = None

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.start_time

    def record_command(self, action: str, success: bool = True) -> None:
        """Record command execution metrics."""
        self.total_commands += 1
        self.last_command = action
        if not success:
            self.error_count += 1

    def update_battery_state(self, level: float, charging: bool) -> None:
        """Update battery telemetry."""
        self.battery_level = max(0.0, min(100.0, level))
        self.is_charging = charging

    def get_heartbeat_payload(self) -> Dict[str, Any]:
        """Construct structured heartbeat packet."""
        return {
            "type": "heartbeat",
            "device_id": self.device_id,
            "platform": "android",
            "status": "online",
            "uptime": f"{self.uptime_seconds:.1f}s",
            "runtime_version": self.runtime_version,
            "telemetry": {
                "battery_level": self.battery_level,
                "battery_charging": self.is_charging,
                "total_commands": self.total_commands,
                "error_count": self.error_count,
                "last_command": self.last_command,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _loop(self) -> None:
        """Periodic heartbeat broadcast loop."""
        while self._running:
            try:
                payload = self.get_heartbeat_payload()
                res = self.send_fn(json.dumps(payload))
                if asyncio.iscoroutine(res):
                    await res
                logger.debug(f"Emitted Android heartbeat for {self.device_id}")
            except Exception as e:
                logger.warning(f"Failed to emit Android heartbeat: {e}")

            await asyncio.sleep(self.interval_seconds)

    def start(self) -> None:
        """Start periodic heartbeat task."""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        """Stop heartbeat loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
