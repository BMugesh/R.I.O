"""Unit and Integration Tests for WebSocket Device Control and Remote Security."""

import asyncio
import json
import pytest
from packages.schemas.devices import DeviceCommand, DeviceObservation
from apps.api.deps import container
from apps.api.routers.ws import manager


@pytest.mark.asyncio
async def test_websocket_manager_device_registration_and_disconnect():
    class MockWebSocket:
        def __init__(self):
            self.sent_messages = []
            self.closed = False

        async def accept(self):
            pass

        async def send_text(self, text: str):
            self.sent_messages.append(text)

        async def close(self):
            self.closed = True

    mock_ws = MockWebSocket()
    await manager.connect(mock_ws)
    assert mock_ws in manager.active_clients

    # Register mock device connection
    dev_id = "test-ws-dev-01"
    manager.device_connections[dev_id] = mock_ws
    assert manager.device_connections[dev_id] == mock_ws

    # Disconnect
    manager.disconnect(mock_ws)
    assert mock_ws not in manager.active_clients
    assert dev_id not in manager.device_connections


@pytest.mark.asyncio
async def test_websocket_command_dispatch_and_observation():
    class MockWebSocket:
        def __init__(self):
            self.sent_messages = []

        async def send_text(self, text: str):
            self.sent_messages.append(json.loads(text))

    mock_ws = MockWebSocket()
    dev_id = "test-device-echo"
    manager.device_connections[dev_id] = mock_ws

    # Background responder simulation
    async def simulate_device_response():
        await asyncio.sleep(0.05)
        # Find pending command id from sent message
        assert len(mock_ws.sent_messages) > 0
        cmd_sent = mock_ws.sent_messages[0]
        cmd_id = cmd_sent["command_id"]

        fut = manager.pending_observations.get(cmd_id)
        if fut and not fut.done():
            fut.set_result({
                "command_id": cmd_id,
                "device_id": dev_id,
                "success": True,
                "action": cmd_sent["action"],
                "data": {"status": "verified", "window_title": "Test App"},
            })

    asyncio.create_task(simulate_device_response())

    cmd = DeviceCommand(
        device_id=dev_id,
        action="open_application",
        parameters={"app_name": "TestApp"},
        timeout_seconds=2.0,
    )

    obs = await manager.dispatch_device_command(dev_id, cmd)
    assert obs is not None
    assert obs.success is True
    assert obs.action == "open_application"
    assert obs.data["window_title"] == "Test App"

    # Cleanup
    manager.device_connections.pop(dev_id, None)
