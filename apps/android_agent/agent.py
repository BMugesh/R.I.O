"""R.I.O. Android Agent (Mobile Bridge Specification and Daemon).

Controls mobile hardware capabilities:
- Camera capture & streaming
- Microphone speech input
- Screen inspection & touch gestures
- Push notifications
- Device location & sensor telemetry
- Application lifecycle management
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Dict, Optional
import websockets
from packages.schemas.devices import (
    Device,
    DeviceAction,
    DeviceCapability,
    DeviceCommand,
    DeviceObservation,
    DeviceStatus,
    DeviceType,
)
from runtime.android.actions import AndroidActionHandler
from runtime.android.device_manager import AndroidDeviceManager
from runtime.android.permissions import AndroidPermissionManager

logger = logging.getLogger("rio.android_agent")


class AndroidAgent:
    """Android Device Agent Bridge."""

    def __init__(
        self,
        device_id: str = "android-01",
        device_name: str = "Pixel Phone",
        core_ws_url: Optional[str] = None,
    ):
        self.device_id = device_id
        self.device_name = device_name
        self.core_ws_url = core_ws_url or os.getenv("CORE_WS_URL", "ws://localhost:8000/ws")
        self.device_manager = AndroidDeviceManager()
        self.permission_manager = AndroidPermissionManager()
        self.action_handler = AndroidActionHandler(device_id=self.device_id)
        self.running = False

    def get_manifest(self) -> Device:
        """Return registered Android device capabilities."""
        return Device(
            device_id=self.device_id,
            name=self.device_name,
            device_name=self.device_name,
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
            permissions=["camera", "microphone", "notifications", "location", "touch", "app_launch"],
            os_info="Android 14 (API 34)",
        )

    async def execute_command(self, command: DeviceCommand) -> DeviceObservation:
        """Handle Android mobile action."""
        action_name = command.action.lower()
        params = command.parameters or {}

        # Permission check
        is_allowed, req_cap, denial_reason = self.permission_manager.is_action_allowed(action_name)
        if not is_allowed:
            return DeviceObservation(
                command_id=command.command_id,
                action_id=command.command_id,
                device_id=self.device_id,
                status="rejected",
                success=False,
                action=command.action,
                error=f"Unauthorized: {denial_reason}",
            )

        # Dispatch typed action
        action_obj = DeviceAction(
            action_id=command.command_id,
            device_id=self.device_id,
            capability=req_cap or "general",
            action_type=action_name,
            parameters=params,
            target=params.get("package") or params.get("target") or params.get("app_name"),
        )
        return await self.action_handler.execute(action_obj)

    async def run(self):
        """Connect to R.I.O. Core WebSocket."""
        self.running = True
        logger.info(f"Starting Android Agent '{self.device_id}'...")
        while self.running:
            try:
                async with websockets.connect(self.core_ws_url) as ws:
                    reg_payload = {
                        "type": "device_register",
                        "device_id": self.device_id,
                        "device_name": self.device_name,
                        "platform": "android",
                        "capabilities": [c.value if hasattr(c, "value") else c for c in self.get_manifest().capabilities],
                        "manifest": self.get_manifest().model_dump(),
                    }
                    await ws.send(json.dumps(reg_payload))
                    logger.info(f"Android device '{self.device_id}' connected.")
                    while self.running:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        if data.get("type") in ("device_command", "command"):
                            cmd_data = data.get("command") or data
                            cmd = DeviceCommand(**cmd_data)
                            obs = await self.execute_command(cmd)
                            resp = {
                                "type": "device_observation",
                                "device_id": self.device_id,
                                "observation": obs.model_dump(),
                            }
                            await ws.send(json.dumps(resp))
            except Exception as e:
                logger.warning(f"Android Agent connection disconnected: {e}. Retrying...")
                await asyncio.sleep(3)


if __name__ == "__main__":
    agent = AndroidAgent()
    asyncio.run(agent.run())

