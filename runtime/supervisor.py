"""R.I.O. Runtime Supervisor and Lifecycle Coordinator.

Coordinates the complete background daemon lifecycle:
Device Identification -> Permission Loading -> Persistent Connection ->
Heartbeats -> Event Listening -> Capability Enforcement -> ComputerAgent Execution ->
Observation Return -> Graceful Shutdown.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import signal
import sys
from typing import Any, Dict, Optional
from agents.computer.agent import ComputerAgent
from packages.schemas.agents import AgentStatus
from packages.schemas.devices import DeviceCommand, DeviceObservation
from packages.schemas.input import InputType, RIOInput
from runtime.connection import ConnectionManager
from runtime.device_manager import DeviceManager
from runtime.event_listener import EventListener, RuntimeEvent
from runtime.health import RuntimeHealth
from runtime.heartbeat import HeartbeatManager
from runtime.permissions import Capability, PermissionManager
from runtime.tray import SystemTrayManager
from voice.manager import VoiceManager

logger = logging.getLogger("rio.runtime.supervisor")


class RuntimeSupervisor:
    """Central daemon coordinator and execution supervisor."""

    def __init__(
        self,
        core_ws_url: Optional[str] = None,
        auth_token: Optional[str] = None,
        heartbeat_interval: float = 20.0,
        enable_tray: bool = True,
        enable_voice: bool = True,
    ):
        self.device_manager = DeviceManager()
        self.permission_manager = PermissionManager()
        self.health = RuntimeHealth(
            device_id=self.device_manager.device_id,
            device_name=self.device_manager.device_name,
        )
        self.health.active_capabilities_count = len(self.permission_manager.get_active_capabilities())
        self.event_listener = EventListener()

        self.computer_agent = ComputerAgent()
        self.enable_tray = enable_tray
        self.enable_voice = enable_voice
        self.tray_manager: Optional[SystemTrayManager] = None
        self.voice_manager: Optional[VoiceManager] = None
        if self.enable_voice:
            self.voice_manager = VoiceManager(
                permission_manager=self.permission_manager,
                event_listener=self.event_listener,
            )

        self.connection_manager = ConnectionManager(
            device_manager=self.device_manager,
            permission_manager=self.permission_manager,
            health=self.health,
            core_ws_url=core_ws_url,
            auth_token=auth_token,
            command_handler=self.handle_incoming_command,
        )

        self.heartbeat_manager = HeartbeatManager(
            device_id=self.device_manager.device_id,
            send_fn=self.connection_manager.send_raw,
            health=self.health,
            interval_seconds=heartbeat_interval,
            runtime_version=self.device_manager.runtime_version,
        )

        self._shutdown_event = asyncio.Event()

    async def handle_incoming_command(self, raw_envelope: Dict[str, Any]) -> None:
        """Validate, permission-check, execute, and observe incoming device command."""
        cmd_dict = raw_envelope.get("command") or raw_envelope
        command_id = cmd_dict.get("command_id") or cmd_dict.get("id", "cmd-01")
        target_device = cmd_dict.get("device_id")
        action = cmd_dict.get("action") or cmd_dict.get("action_type", "")
        params = cmd_dict.get("parameters") or {}

        # 1. Validate Target Device
        if target_device and target_device != self.device_manager.device_id:
            logger.warning(f"Ignoring command for foreign device '{target_device}' (Local: '{self.device_manager.device_id}')")
            return

        # 2. Permission Check
        is_allowed, req_cap = self.permission_manager.is_action_allowed(action)
        if not is_allowed:
            err_msg = f"Unauthorized: Action '{action}' requires capability '{req_cap}', which is disabled in permissions."
            logger.warning(err_msg)
            self.health.record_error(err_msg)
            obs = DeviceObservation(
                command_id=command_id,
                device_id=self.device_manager.device_id,
                success=False,
                action=action,
                error=err_msg,
            )
            await self.connection_manager.send_observation(obs.model_dump())
            await self.event_listener.emit(RuntimeEvent("command_rejected", {"action": action, "reason": err_msg}))
            return

        # 3. Execute via ComputerAgent
        logger.info(f"Executing authorized command: {action} (Capability: {req_cap})")
        await self.event_listener.emit(RuntimeEvent("command_received", {"action": action, "command_id": command_id}))

        try:
            # Prepare payload for ComputerAgent
            exec_payload = dict(params)
            exec_payload["action_type"] = action
            rio_in = RIOInput(type=InputType.TEXT, payload=exec_payload)

            agent_res = await self.computer_agent.run(rio_in, context={})
            success = agent_res.status == AgentStatus.SUCCESS

            obs = DeviceObservation(
                command_id=command_id,
                device_id=self.device_manager.device_id,
                success=success,
                action=action,
                data=agent_res.data,
                error=agent_res.message if not success else None,
            )

            # Transmit observation back to Core
            await self.connection_manager.send_observation(obs.model_dump())
            self.health.record_command(action, success=success)
            await self.event_listener.emit(RuntimeEvent("command_executed", {"action": action, "success": success}))

        except Exception as e:
            logger.error(f"Error executing command '{action}': {e}")
            self.health.record_command(action, success=False)
            obs = DeviceObservation(
                command_id=command_id,
                device_id=self.device_manager.device_id,
                success=False,
                action=action,
                error=str(e),
            )
            await self.connection_manager.send_observation(obs.model_dump())

    async def run(self) -> None:
        """Start all runtime components and run until shutdown."""
        logger.info("⚡ Starting R.I.O. Background Runtime Supervisor...")
        await self.event_listener.emit(RuntimeEvent("runtime_started", {"device_id": self.device_manager.device_id}))

        # Start Heartbeat
        self.heartbeat_manager.start()

        # Start Voice Interface (if enabled and permitted)
        if self.enable_voice and self.voice_manager:
            if self.permission_manager.is_permitted(Capability.MICROPHONE_READ):
                await self.voice_manager.start()
            else:
                logger.info("🎙️ Voice interface disabled by permission boundary ('microphone.read' is false).")

        # Start System Tray (if enabled)
        if self.enable_tray:
            self.tray_manager = SystemTrayManager(
                on_quit=self.request_shutdown,
                get_status_fn=lambda: self.health.connection_status.upper(),
            )
            self.tray_manager.start()

        # Run connection task
        conn_task = asyncio.create_task(self.connection_manager.start())

        try:
            await self._shutdown_event.wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Shutdown signal received.")

        # Clean Shutdown Sequence
        logger.info("🛑 Executing clean runtime shutdown sequence...")
        if self.voice_manager:
            await self.voice_manager.stop()
        self.heartbeat_manager.stop()
        self.connection_manager.stop()
        if self.tray_manager:
            self.tray_manager.stop()

        if not conn_task.done():
            conn_task.cancel()
            try:
                await conn_task
            except asyncio.CancelledError:
                pass

        await self.event_listener.emit(RuntimeEvent("runtime_stopped", {"device_id": self.device_manager.device_id}))
        self.health.set_connection_status("offline")
        logger.info("R.I.O. Runtime cleanly terminated.")

    def request_shutdown(self) -> None:
        """Signal the supervisor to initiate clean shutdown."""
        self._shutdown_event.set()
