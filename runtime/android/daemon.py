"""R.I.O. Android Runtime Daemon & Supervisor.

Coordinates the complete mobile runtime lifecycle:
Persistent Identity -> Dual-Permission Enforcement -> Secure WebSocket Connectivity ->
Heartbeat & Battery Telemetry -> Typed Action Dispatch -> Layered Observation Return -> Clean Shutdown.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Dict, Optional
from packages.schemas.devices import DeviceAction, DeviceObservation
from runtime.android.actions import AndroidActionHandler
from runtime.android.connection import AndroidConnectionManager
from runtime.android.device_manager import AndroidDeviceManager
from runtime.android.heartbeat import AndroidHeartbeatManager
from runtime.android.permissions import AndroidPermissionManager

logger = logging.getLogger("rio.android.daemon")


class AndroidRuntimeDaemon:
    """Central daemon coordinator for Android R.I.O. Runtime."""

    def __init__(
        self,
        core_ws_url: Optional[str] = None,
        auth_token: Optional[str] = None,
        heartbeat_interval: float = 20.0,
    ):
        self.device_manager = AndroidDeviceManager()
        self.permission_manager = AndroidPermissionManager()
        self.action_handler = AndroidActionHandler(device_id=self.device_manager.device_id)

        self.connection_manager = AndroidConnectionManager(
            device_manager=self.device_manager,
            permission_manager=self.permission_manager,
            core_ws_url=core_ws_url,
            auth_token=auth_token,
            command_handler=self.handle_incoming_command,
        )

        self.heartbeat_manager = AndroidHeartbeatManager(
            device_id=self.device_manager.device_id,
            send_fn=self.connection_manager.send_raw,
            interval_seconds=heartbeat_interval,
            runtime_version=self.device_manager.runtime_version,
        )

        self._shutdown_event = asyncio.Event()

    async def handle_incoming_command(self, raw_envelope: Dict[str, Any]) -> None:
        """Process, permission-check, execute, and reply to incoming command from Core."""
        cmd_dict = raw_envelope.get("command") or raw_envelope
        command_id = cmd_dict.get("command_id") or cmd_dict.get("action_id", "cmd-01")
        target_device = cmd_dict.get("device_id")
        action_name = cmd_dict.get("action") or cmd_dict.get("action_type", "")
        params = cmd_dict.get("parameters") or {}

        # 1. Validate Target Device Identity
        if target_device and target_device != self.device_manager.device_id:
            logger.warning(f"Android daemon ignoring command targeted for '{target_device}' (Local: '{self.device_manager.device_id}')")
            return

        # 2. Dual-Permission Check (R.I.O. Policy + Android OS Permission)
        is_allowed, req_cap, denial_reason = self.permission_manager.is_action_allowed(action_name)
        if not is_allowed:
            err_msg = f"Unauthorized: {denial_reason}"
            logger.warning(err_msg)
            self.heartbeat_manager.record_command(action_name, success=False)
            obs = DeviceObservation(
                command_id=command_id,
                action_id=command_id,
                device_id=self.device_manager.device_id,
                status="rejected",
                success=False,
                action=action_name,
                error=err_msg,
            )
            await self.connection_manager.send_observation(obs.model_dump())
            return

        # 3. Execute Typed Action via AndroidActionHandler
        logger.info(f"Android daemon executing authorized action: '{action_name}' (Capability: {req_cap})")
        action_obj = DeviceAction(
            action_id=command_id,
            device_id=self.device_manager.device_id,
            capability=req_cap or "general",
            action_type=action_name,
            parameters=params,
            target=params.get("package") or params.get("target"),
        )

        obs = await self.action_handler.execute(action_obj)
        self.heartbeat_manager.record_command(action_name, success=obs.success)

        # Transmit observation back to Core
        await self.connection_manager.send_observation(obs.model_dump())

    async def start(self) -> None:
        """Run the Android daemon service."""
        logger.info(f"📱 Starting R.I.O. Android Runtime Daemon for device '{self.device_manager.device_id}'...")
        self.heartbeat_manager.start()
        conn_task = asyncio.create_task(self.connection_manager.start())

        try:
            await self._shutdown_event.wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Android daemon shutdown signal received.")

        # Clean shutdown
        self.heartbeat_manager.stop()
        self.connection_manager.stop()

        if not conn_task.done():
            conn_task.cancel()
            try:
                await conn_task
            except asyncio.CancelledError:
                pass

        logger.info("📱 Android Runtime Daemon stopped cleanly.")

    def stop(self) -> None:
        """Request daemon shutdown."""
        self._shutdown_event.set()


if __name__ == "__main__":
    daemon = AndroidRuntimeDaemon()
    asyncio.run(daemon.start())
