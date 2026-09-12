import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Dict, Optional, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from packages.schemas.chat import ChatRequest, ChatStreamChunk
from packages.schemas.devices import Device, DeviceCapability, DeviceCommand, DeviceObservation, DeviceStatus, DeviceType
from packages.schemas.events import EventType, RIOEvent
from packages.schemas.safety import ApprovalDecision, ApprovalStatus
from apps.api.deps import container
from apps.api.routers.devices import _registered_devices

logger = logging.getLogger("rio.ws")
router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    """Manages active WebSocket connections for UI clients and device runtimes."""

    def __init__(self):
        self.active_clients: Set[WebSocket] = set()
        self.device_connections: Dict[str, WebSocket] = {}
        self.pending_observations: Dict[str, asyncio.Future] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_clients.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_clients.discard(websocket)
        for dev_id, ws in list(self.device_connections.items()):
            if ws == websocket:
                del self.device_connections[dev_id]
                container.device_registry.disconnect_device(dev_id)
                if dev_id in _registered_devices:
                    _registered_devices[dev_id].status = DeviceStatus.OFFLINE

    async def send_chunk(self, websocket: WebSocket, chunk: ChatStreamChunk):
        try:
            await websocket.send_text(json.dumps(chunk.model_dump()))
        except Exception:
            pass

    async def dispatch_device_command(self, device_id: str, command: DeviceCommand) -> Optional[DeviceObservation]:
        """Dispatch a command to a connected device runtime and await observation."""
        ws = self.device_connections.get(device_id)
        if not ws:
            logger.warning(f"Device '{device_id}' is not connected via WebSocket.")
            return None

        cmd_id = command.command_id
        fut = asyncio.get_running_loop().create_future()
        self.pending_observations[cmd_id] = fut

        try:
            payload = {
                "type": "device_command",
                "command_id": cmd_id,
                "device_id": device_id,
                "action": command.action,
                "parameters": command.parameters,
                "timeout_seconds": command.timeout_seconds,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await ws.send_text(json.dumps(payload))
            obs_dict = await asyncio.wait_for(fut, timeout=command.timeout_seconds)
            return DeviceObservation(**obs_dict) if isinstance(obs_dict, dict) else obs_dict
        except asyncio.TimeoutError:
            logger.error(f"Device command {cmd_id} timed out waiting for observation.")
            return DeviceObservation(
                command_id=cmd_id,
                device_id=device_id,
                success=False,
                action=command.action,
                status="uncertain",
                error="Command execution timed out.",
            )
        finally:
            self.pending_observations.pop(cmd_id, None)


manager = ConnectionManager()


@router.get("/ws", tags=["WebSocket"])
async def ws_http_info():
    """Informational endpoint for users who navigate to /ws via HTTP browser."""
    return {
        "service": "R.I.O. WebSocket Gateway",
        "status": "online",
        "protocol": "WebSocket (ws:// or wss://)",
        "message": "This endpoint is for real-time WebSocket client connections (ws://), not direct HTTP browser navigation.",
        "user_interfaces": {
            "web_app": "Open http://<host-ip>:3000 in your browser to access R.I.O. Web UI",
            "api_docs": "Open http://<host-ip>:8000/docs for interactive REST documentation",
        },
        "connected_devices": list(manager.device_connections.keys()),
    }


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Unified WebSocket streaming endpoint."""
    await manager.connect(websocket)
    try:
        while True:
            raw_text = await websocket.receive_text()
            data = json.loads(raw_text)
            msg_type = data.get("type", "user_message")

            # 1. Device Registration Handshake
            if msg_type == "device_register":
                device_id = data.get("device_id", "desktop-01")
                manifest_data = data.get("manifest") or {}
                token = data.get("token")

                # Optional token validation if configured
                expected_token = os.getenv("RIO_AUTH_TOKEN") or os.getenv("RIO_DEVICE_SECRET")
                if expected_token and token and token != expected_token:
                    logger.warning(f"Device '{device_id}' registration failed authentication.")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "error": "Device authentication failed: invalid token.",
                    }))
                    continue

                manager.device_connections[device_id] = websocket

                # Parse capabilities
                raw_caps = data.get("capabilities") or manifest_data.get("capabilities", [])
                cap_list = []
                for c in raw_caps:
                    try:
                        cap_list.append(DeviceCapability(c) if isinstance(c, str) and c in [e.value for e in DeviceCapability] else c)
                    except ValueError:
                        cap_list.append(c)

                dev_platform = (data.get("platform") or manifest_data.get("platform") or "windows").lower()
                dev_type = DeviceType.ANDROID if "android" in dev_platform else (
                    DeviceType.DESKTOP if "windows" in dev_platform else DeviceType.LAPTOP
                )

                registered_dev = Device(
                    device_id=device_id,
                    name=data.get("device_name") or manifest_data.get("name", "Workstation"),
                    device_name=data.get("device_name") or manifest_data.get("name", "Workstation"),
                    type=dev_type,
                    platform=dev_platform,
                    status=DeviceStatus.ONLINE,
                    connection_state="online",
                    capabilities=cap_list,
                    permissions=data.get("permissions") or manifest_data.get("permissions", []),
                    os_info=data.get("platform_version") or manifest_data.get("os_info", "Windows 11"),
                    last_seen=datetime.now(timezone.utc).isoformat(),
                    metadata={
                        "runtime_version": data.get("runtime_version") or manifest_data.get("runtime_version", "0.2.1-dev"),
                        "architecture": data.get("architecture") or manifest_data.get("architecture"),
                    },
                )
                container.device_registry.register_device(registered_dev)
                _registered_devices[device_id] = registered_dev

                logger.info(f"Device '{device_id}' registered and online.")
                await websocket.send_text(json.dumps({
                    "type": "device_registered",
                    "device_id": device_id,
                    "status": "online",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))
                continue

            # 2. Heartbeat Handling
            if msg_type == "heartbeat":
                device_id = data.get("device_id")
                if device_id:
                    container.device_registry.record_heartbeat(device_id, metadata=data.get("telemetry") or {})
                    if device_id in _registered_devices:
                        _registered_devices[device_id].last_seen = datetime.now(timezone.utc).isoformat()
                        _registered_devices[device_id].status = DeviceStatus.ONLINE
                continue

            # 3. Device Observation Reply
            if msg_type == "device_observation":
                obs_data = data.get("observation") or data
                cmd_id = obs_data.get("command_id") or obs_data.get("action_id")
                if cmd_id and cmd_id in manager.pending_observations:
                    fut = manager.pending_observations[cmd_id]
                    if not fut.done():
                        fut.set_result(obs_data)
                continue

            # 4. Human Approval Decision from UI Modal
            if msg_type == "approval_decision":
                req_id = data.get("request_id")
                decision_str = data.get("decision", "denied")
                decision_enum = ApprovalStatus.APPROVED if decision_str.lower() == "approved" else ApprovalStatus.DENIED
                container.approval_engine.resolve_decision(
                    ApprovalDecision(
                        request_id=req_id,
                        decision=decision_enum,
                        reason=data.get("reason"),
                    )
                )
                continue

            # 5. User Chat Message / Task Submission
            if msg_type == "user_message":
                user_msg = data.get("message", "")
                session_id = data.get("session_id", "default_session")
                dev_mode = data.get("developer_mode", False)

                # Send initial status indicator
                await manager.send_chunk(
                    websocket,
                    ChatStreamChunk(chunk_type="status_update", task_status="Reasoning & planning..."),
                )

                # Process via central Orchestrator
                chat_req = ChatRequest(
                    message=user_msg,
                    session_id=session_id,
                    developer_mode=dev_mode,
                    device_id=data.get("device_id") or data.get("deviceId"),
                    origin_device_id=data.get("origin_device_id") or data.get("originDeviceId"),
                    interface_type=data.get("interface_type") or data.get("interfaceType") or "web",
                    origin_context=data.get("origin_context") or data.get("originContext"),
                )


                response = await container.orchestrator.process_chat(chat_req)

                # Stream response back
                await manager.send_chunk(
                    websocket,
                    ChatStreamChunk(
                        chunk_type="done",
                        content=response.reply,
                        task_status=response.status,
                        developer_trace=response.developer_trace,
                    ),
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

