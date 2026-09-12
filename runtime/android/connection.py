"""R.I.O. Android WebSocket Connection Manager.

Maintains a persistent, resilient, authenticated WebSocket connection to R.I.O. Core
with exponential backoff reconnection and explicit lifecycle state transitions.
"""

import asyncio
from datetime import datetime, timezone
from enum import Enum
import json
import logging
import os
from typing import Any, Callable, Dict, Optional
import websockets
from runtime.android.device_manager import AndroidDeviceManager
from runtime.android.permissions import AndroidPermissionManager

logger = logging.getLogger("rio.android.connection")


class AndroidLifecycleState(str, Enum):
    STOPPED = "STOPPED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    AUTHENTICATED = "AUTHENTICATED"
    REGISTERED = "REGISTERED"
    ONLINE = "ONLINE"
    DISCONNECTED = "DISCONNECTED"
    RECONNECTING = "RECONNECTING"


class AndroidConnectionManager:
    """Manages resilient WebSocket connectivity for Android R.I.O. devices."""

    def __init__(
        self,
        device_manager: AndroidDeviceManager,
        permission_manager: AndroidPermissionManager,
        core_ws_url: Optional[str] = None,
        auth_token: Optional[str] = None,
        command_handler: Optional[Callable[[Dict[str, Any]], Any]] = None,
        initial_retry_delay: float = 1.0,
        max_retry_delay: float = 60.0,
    ):
        self.device_manager = device_manager
        self.permission_manager = permission_manager
        self.core_ws_url = core_ws_url or os.getenv("CORE_WS_URL", "ws://localhost:8000/ws")
        self.auth_token = auth_token or os.getenv("RIO_AUTH_TOKEN", "rio_secret")
        self.command_handler = command_handler
        self.initial_retry_delay = initial_retry_delay
        self.max_retry_delay = max_retry_delay

        self.state: AndroidLifecycleState = AndroidLifecycleState.STOPPED
        self._running = False
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected_event = asyncio.Event()

    @property
    def is_connected(self) -> bool:
        if self._ws is None:
            return False
        if hasattr(self._ws, "state"):
            try:
                return getattr(self._ws.state, "name", "") == "OPEN" or self._ws.state == 1
            except Exception:
                pass
        if hasattr(self._ws, "closed"):
            return not self._ws.closed
        if hasattr(self._ws, "open"):
            return bool(self._ws.open)
        return True

    def set_state(self, new_state: AndroidLifecycleState) -> None:
        """Update connection lifecycle state."""
        prev = self.state
        self.state = new_state
        logger.info(f"Android Connection State Transition: {prev.value} -> {new_state.value}")

    async def send_raw(self, message: str) -> bool:
        """Send a raw text payload over active WebSocket."""
        if self.is_connected and self._ws:
            try:
                await self._ws.send(message)
                return True
            except Exception as e:
                logger.warning(f"Error sending payload over Android WebSocket: {e}")
                return False
        return False

    async def send_observation(self, observation_payload: Dict[str, Any]) -> bool:
        """Send a structured mobile observation back to R.I.O. Core."""
        envelope = {
            "type": "device_observation",
            "device_id": self.device_manager.device_id,
            "observation": observation_payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return await self.send_raw(json.dumps(envelope))

    async def start(self) -> None:
        """Main persistent lifecycle connection loop."""
        self._running = True
        retry_delay = self.initial_retry_delay

        logger.info(f"Starting Android Connection Manager to Core at {self.core_ws_url}...")

        while self._running:
            try:
                self.set_state(AndroidLifecycleState.CONNECTING)
                async with websockets.connect(
                    self.core_ws_url,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                ) as ws:
                    self._ws = ws
                    self.set_state(AndroidLifecycleState.CONNECTED)
                    retry_delay = self.initial_retry_delay

                    # 1. Device Registration & Authentication Handshake
                    active_caps = self.permission_manager.get_active_capabilities()
                    all_perms = [f"{k}:{v}" for k, v in self.permission_manager.get_all_permissions().items()]
                    reg_payload = self.device_manager.get_registration_payload(
                        capabilities=active_caps,
                        permissions=all_perms,
                    )
                    if self.auth_token:
                        reg_payload["token"] = self.auth_token

                    await ws.send(json.dumps(reg_payload))
                    self.set_state(AndroidLifecycleState.AUTHENTICATED)

                    # 2. Receive loop
                    while self._running:
                        try:
                            raw_msg = await ws.recv()
                            data = json.loads(raw_msg)
                            msg_type = data.get("type")

                            if msg_type == "device_registered":
                                self.set_state(AndroidLifecycleState.REGISTERED)
                                self.set_state(AndroidLifecycleState.ONLINE)
                                self._connected_event.set()
                                logger.info(f"Android device '{self.device_manager.device_id}' registered successfully.")

                            elif msg_type in ("device_command", "command"):
                                logger.info(f"Received mobile command: {data.get('action')}")
                                if self.command_handler:
                                    res = self.command_handler(data)
                                    if asyncio.iscoroutine(res):
                                        await res

                            elif msg_type == "ping":
                                await ws.send(json.dumps({"type": "pong", "device_id": self.device_manager.device_id}))

                        except websockets.ConnectionClosed:
                            logger.warning("WebSocket closed by R.I.O. Core.")
                            break
                        except json.JSONDecodeError:
                            logger.warning("Received invalid JSON from Core.")

            except (websockets.WebSocketException, OSError, asyncio.TimeoutError) as e:
                self.set_state(AndroidLifecycleState.DISCONNECTED)
                logger.warning(f"Connection failed ({e}). Reconnecting in {retry_delay:.1f}s...")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.set_state(AndroidLifecycleState.DISCONNECTED)
                logger.error(f"Unexpected connection error: {e}. Retrying in {retry_delay:.1f}s...")

            self._ws = None
            self._connected_event.clear()

            if not self._running:
                break

            self.set_state(AndroidLifecycleState.RECONNECTING)
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2.0, self.max_retry_delay)

        self.set_state(AndroidLifecycleState.STOPPED)
        logger.info("Android Connection Manager terminated.")

    def stop(self) -> None:
        """Signal connection manager to cleanly shut down."""
        self._running = False
        if self._ws:
            try:
                if self.is_connected:
                    asyncio.create_task(self._ws.close())
            except Exception:
                pass
