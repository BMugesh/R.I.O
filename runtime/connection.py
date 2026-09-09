"""R.I.O. Persistent WebSocket Connection Manager.

Maintains an always-on, resilient bidirectional connection to R.I.O. Core.
Implements exponential backoff reconnection, device registration handshake,
and secure command and observation dispatching.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Callable, Dict, Optional
import websockets
from runtime.device_manager import DeviceManager
from runtime.health import RuntimeHealth
from runtime.permissions import PermissionManager

logger = logging.getLogger("rio.runtime.connection")


class ConnectionManager:
    """Manages resilient persistent WebSocket connectivity to R.I.O. Core."""

    def __init__(
        self,
        device_manager: DeviceManager,
        permission_manager: PermissionManager,
        health: RuntimeHealth,
        core_ws_url: Optional[str] = None,
        auth_token: Optional[str] = None,
        command_handler: Optional[Callable[[Dict[str, Any]], Any]] = None,
        initial_retry_delay: float = 1.0,
        max_retry_delay: float = 60.0,
    ):
        self.device_manager = device_manager
        self.permission_manager = permission_manager
        self.health = health
        self.core_ws_url = core_ws_url or os.getenv("CORE_WS_URL", "ws://localhost:8000/ws")
        self.auth_token = auth_token or os.getenv("RIO_AUTH_TOKEN", "rio_secret")
        self.command_handler = command_handler
        self.initial_retry_delay = initial_retry_delay
        self.max_retry_delay = max_retry_delay

        self._running = False
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected_event = asyncio.Event()

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

    async def send_raw(self, message: str) -> bool:
        """Send a raw text payload over the active WebSocket."""
        if self.is_connected and self._ws:
            try:
                await self._ws.send(message)
                return True
            except Exception as e:
                logger.warning(f"Error sending message over WebSocket: {e}")
                return False
        return False

    async def send_observation(self, observation_payload: Dict[str, Any]) -> bool:
        """Send a structured device observation response back to R.I.O. Core."""
        envelope = {
            "type": "device_observation",
            "device_id": self.device_manager.device_id,
            "observation": observation_payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return await self.send_raw(json.dumps(envelope))

    async def start(self) -> None:
        """Main persistent connection lifecycle loop."""
        self._running = True
        retry_delay = self.initial_retry_delay

        logger.info(f"R.I.O. Connection Manager started. Target Core: {self.core_ws_url}")

        while self._running:
            try:
                self.health.set_connection_status("connecting", self.core_ws_url)
                logger.info(f"Connecting to R.I.O. Core at {self.core_ws_url}...")

                async with websockets.connect(
                    self.core_ws_url,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                ) as ws:
                    self._ws = ws
                    self._connected_event.set()
                    self.health.set_connection_status("online", self.core_ws_url)
                    retry_delay = self.initial_retry_delay  # Reset backoff on success

                    # 1. Device Registration Handshake
                    active_caps = self.permission_manager.get_active_capabilities()
                    all_perms = [f"{k}:{v}" for k, v in self.permission_manager.get_all_permissions().items()]
                    reg_payload = self.device_manager.get_registration_payload(
                        capabilities=active_caps,
                        permissions=all_perms,
                    )
                    if self.auth_token:
                        reg_payload["token"] = self.auth_token

                    await ws.send(json.dumps(reg_payload))
                    logger.info(f"Registered device '{self.device_manager.device_id}' with R.I.O. Core.")

                    # 2. Message Receive Loop
                    while self._running:
                        try:
                            raw_msg = await ws.recv()
                            data = json.loads(raw_msg)
                            msg_type = data.get("type")

                            if msg_type == "device_registered":
                                logger.info(f"Registration confirmed by Core: {data}")
                            elif msg_type in ("device_command", "command"):
                                logger.info(f"Received device command: {data.get('action') or data.get('command')}")
                                if self.command_handler:
                                    res = self.command_handler(data)
                                    if asyncio.iscoroutine(res):
                                        await res
                            elif msg_type == "ping":
                                await ws.send(json.dumps({"type": "pong", "device_id": self.device_manager.device_id}))
                        except websockets.ConnectionClosed:
                            logger.warning("WebSocket connection closed by Core.")
                            break
                        except json.JSONDecodeError:
                            logger.warning("Received invalid JSON from Core.")

            except (websockets.WebSocketException, OSError, asyncio.TimeoutError) as e:
                self.health.set_connection_status("offline")
                self.health.record_reconnect_attempt()
                logger.warning(f"Connection failed ({e}). Retrying in {retry_delay:.1f}s...")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.health.set_connection_status("error")
                self.health.record_error(str(e))
                logger.error(f"Unexpected error in connection loop: {e}. Retrying in {retry_delay:.1f}s...")

            self._ws = None
            self._connected_event.clear()

            if not self._running:
                break

            # Exponential backoff sleep
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2.0, self.max_retry_delay)

        self.health.set_connection_status("offline")
        logger.info("R.I.O. Connection Manager stopped.")

    def stop(self) -> None:
        """Signal the connection manager to stop and close open sockets."""
        self._running = False
        if self._ws and not self._ws.closed:
            asyncio.create_task(self._ws.close())
