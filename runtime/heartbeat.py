"""R.I.O. Runtime Heartbeat Generator.

Maintains presence with R.I.O. Core by periodically sending non-invasive health
telemetry and device status updates over the persistent WebSocket channel.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Callable, Optional
from runtime.health import RuntimeHealth


logger = logging.getLogger("rio.runtime.heartbeat")


class HeartbeatManager:
    """Manages periodic heartbeat transmission to R.I.O. Core."""

    def __init__(
        self,
        device_id: str,
        send_fn: Callable[[str], Any],
        health: RuntimeHealth,
        interval_seconds: float = 20.0,
        runtime_version: str = "1.0.0",
    ):
        self.device_id = device_id
        self.send_fn = send_fn
        self.health = health
        self.interval_seconds = interval_seconds
        self.runtime_version = runtime_version
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        """Start the background heartbeat task."""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._heartbeat_loop())
            logger.info(f"Heartbeat loop started (interval: {self.interval_seconds}s).")

    def stop(self) -> None:
        """Stop the background heartbeat task."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("Heartbeat loop stopped.")

    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat dispatch loop."""
        while self._running:
            try:
                payload = {
                    "type": "heartbeat",
                    "device_id": self.device_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "online",
                    "uptime_seconds": self.health.uptime_seconds,
                    "runtime_version": self.runtime_version,
                    "capabilities_count": self.health.active_capabilities_count,
                    "total_commands": self.health.total_commands,
                    "error_count": self.health.error_count,
                }
                raw_msg = json.dumps(payload)
                res = self.send_fn(raw_msg)
                if asyncio.iscoroutine(res):
                    await res

                self.health.record_heartbeat()
                logger.debug(f"Heartbeat sent for {self.device_id}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Failed to transmit heartbeat: {e}")

            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break
