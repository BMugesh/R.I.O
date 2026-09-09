"""Comprehensive Unit and Integration Tests for R.I.O. Background Runtime."""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import pytest
from packages.schemas.agents import AgentStatus
from packages.schemas.devices import DeviceCommand, DeviceObservation
from runtime.connection import ConnectionManager
from runtime.device_manager import DeviceManager
from runtime.event_listener import EventListener, RuntimeEvent
from runtime.health import RuntimeHealth
from runtime.heartbeat import HeartbeatManager
from runtime.permissions import Capability, DEFAULT_PERMISSIONS, PermissionManager
from runtime.supervisor import RuntimeSupervisor
from runtime.windows import disable_autostart, enable_autostart, is_autostart_enabled


# 1. Device Manager Tests
def test_device_manager_stable_identity_persistence():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        dm1 = DeviceManager(config_dir=tmp_path)
        id1 = dm1.device_id
        assert id1.startswith("device-")
        assert dm1.device_name != ""
        assert dm1.runtime_version == "1.0.0"

        # Second instance on same config dir must recover identical device_id
        dm2 = DeviceManager(config_dir=tmp_path)
        assert dm2.device_id == id1

        # Registration payload check
        reg = dm2.get_registration_payload(capabilities=["screen.read"], permissions=["screen.read:true"])
        assert reg["type"] == "device_register"
        assert reg["device_id"] == id1
        assert "capabilities" in reg


# 2. Permission Manager Tests
def test_permission_manager_defaults_and_toggles():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        pm = PermissionManager(config_dir=tmp_path)

        # Check default least privilege
        assert pm.is_permitted(Capability.SCREEN_READ) is True
        assert pm.is_permitted(Capability.APPLICATION_LAUNCH) is True
        assert pm.is_permitted(Capability.FILESYSTEM_WRITE) is False
        assert pm.is_permitted(Capability.MICROPHONE_READ) is False

        # Action to capability mapping
        allowed, cap = pm.is_action_allowed("open_application")
        assert allowed is True
        assert cap == Capability.APPLICATION_LAUNCH

        allowed, cap = pm.is_action_allowed("write_file")
        assert allowed is False
        assert cap == Capability.FILESYSTEM_WRITE

        # Toggle permission
        pm.set_permission(Capability.FILESYSTEM_WRITE, True)
        assert pm.is_permitted(Capability.FILESYSTEM_WRITE) is True
        allowed, _ = pm.is_action_allowed("write_file")
        assert allowed is True

        # Re-load from disk
        pm2 = PermissionManager(config_dir=tmp_path)
        assert pm2.is_permitted(Capability.FILESYSTEM_WRITE) is True


# 3. Health Tracker Tests
def test_runtime_health_tracking_and_persistence():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        health = RuntimeHealth(device_id="test-dev-01", device_name="TestBox", config_dir=tmp_path)

        assert health.device_id == "test-dev-01"
        assert health.uptime_seconds >= 0.0

        health.set_connection_status("online", "ws://localhost:8000/ws")
        health.record_heartbeat()
        health.record_command("screenshot", success=True)
        health.record_command("write_file", success=False)

        assert health.total_commands == 2
        assert health.error_count == 1
        assert health.last_command_action == "write_file"

        # Read persisted snapshot
        persisted = RuntimeHealth.read_persisted_health(config_dir=tmp_path)
        assert persisted is not None
        assert persisted["status"] == "ONLINE"
        assert persisted["total_commands"] == 2
        assert persisted["error_count"] == 1


# 4. Event Listener Tests
@pytest.mark.asyncio
async def test_event_listener_bus():
    listener = EventListener()
    received_events = []

    def on_custom_event(ev: RuntimeEvent):
        received_events.append(ev)

    listener.subscribe("test_event", on_custom_event)

    ev1 = RuntimeEvent("test_event", {"val": 42})
    await listener.emit(ev1)

    assert len(received_events) == 1
    assert received_events[0].payload["val"] == 42


# 5. Heartbeat Manager Tests
@pytest.mark.asyncio
async def test_heartbeat_emission():
    with tempfile.TemporaryDirectory() as tmp_dir:
        health = RuntimeHealth(device_id="dev-hb-01", config_dir=Path(tmp_dir))
        sent_messages = []

        async def mock_send(msg: str):
            sent_messages.append(json.loads(msg))

        hb = HeartbeatManager(
            device_id="dev-hb-01",
            send_fn=mock_send,
            health=health,
            interval_seconds=0.1,
        )

        hb.start()
        await asyncio.sleep(0.35)
        hb.stop()

        assert len(sent_messages) >= 2
        first_hb = sent_messages[0]
        assert first_hb["type"] == "heartbeat"
        assert first_hb["device_id"] == "dev-hb-01"
        assert first_hb["status"] == "online"


# 6. Supervisor & Permission Security Tests
@pytest.mark.asyncio
async def test_supervisor_command_authorization_and_rejection():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        supervisor = RuntimeSupervisor(enable_tray=False)
        # Override config dirs for testing isolation
        supervisor.device_manager = DeviceManager(config_dir=tmp_path)
        supervisor.permission_manager = PermissionManager(config_dir=tmp_path)
        supervisor.health = RuntimeHealth(device_id=supervisor.device_manager.device_id, config_dir=tmp_path)

        sent_observations = []

        async def mock_send_obs(envelope):
            sent_observations.append(envelope)

        supervisor.connection_manager.send_observation = mock_send_obs

        # Test A: Allowed command (application.launch / open_application)
        cmd_launch = {
            "command_id": "cmd-001",
            "device_id": supervisor.device_manager.device_id,
            "action": "open_application",
            "parameters": {"app_name": "notepad"},
        }
        await supervisor.handle_incoming_command(cmd_launch)

        assert len(sent_observations) == 1
        obs1 = sent_observations[0]
        assert obs1["success"] is True
        assert obs1["action"] == "open_application"

        # Test B: Unauthorized command (filesystem.write is false by default)
        cmd_write = {
            "command_id": "cmd-002",
            "device_id": supervisor.device_manager.device_id,
            "action": "write_file",
            "parameters": {"path": "test.txt", "content": "hello"},
        }
        await supervisor.handle_incoming_command(cmd_write)

        assert len(sent_observations) == 2
        obs2 = sent_observations[1]
        assert obs2["success"] is False
        assert "Unauthorized" in obs2["error"]


        # Test C: Foreign device command (should be ignored without sending observation)
        cmd_foreign = {
            "command_id": "cmd-003",
            "device_id": "other-device-999",
            "action": "screenshot",
        }
        await supervisor.handle_incoming_command(cmd_foreign)
        assert len(sent_observations) == 2  # Not incremented


# 7. Windows Autostart Registration Tests
def test_windows_autostart_toggle():
    import platform
    if platform.system() == "Windows":
        # Test enable then disable
        enabled = enable_autostart()
        assert enabled is True
        assert is_autostart_enabled() is True

        disabled = disable_autostart()
        assert disabled is True
        assert is_autostart_enabled() is False
