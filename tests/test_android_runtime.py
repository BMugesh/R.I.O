"""Comprehensive Unit Tests for Android Device Runtime Architecture."""
import pytest
pytestmark = pytest.mark.hardware



import asyncio
import json
from pathlib import Path
import tempfile
import pytest
from packages.schemas.devices import DeviceAction, DeviceObservation
from runtime.android.actions import AndroidAccessLevel, AndroidActionHandler
from runtime.android.connection import AndroidConnectionManager, AndroidLifecycleState
from runtime.android.device_manager import AndroidDeviceManager
from runtime.android.heartbeat import AndroidHeartbeatManager
from runtime.android.permissions import AndroidCapability, AndroidPermissionManager


def test_android_device_manager_identity():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        dm1 = AndroidDeviceManager(storage_dir=tmp_path)
        id1 = dm1.device_id
        assert id1.startswith("rio-phone-")
        assert dm1.platform_version.startswith("Android")

        # Persistence reload
        dm2 = AndroidDeviceManager(storage_dir=tmp_path)
        assert dm2.device_id == id1

        # Registration payload check
        payload = dm2.get_registration_payload(capabilities=["screen.read"], permissions=["screen.read:true"])
        assert payload["type"] == "device_register"
        assert payload["platform"] == "android"
        assert payload["device_id"] == id1


def test_android_permissions_dual_check():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        pm = AndroidPermissionManager(storage_dir=tmp_path)

        # Default allowed capability (e.g. application.launch)
        avail, reason = pm.is_capability_available(AndroidCapability.APPLICATION_LAUNCH.value)
        assert avail is True
        assert reason is None

        # Deny R.I.O. permission layer
        pm.set_rio_permission(AndroidCapability.CAMERA_READ.value, False)
        avail_cam, reason_cam = pm.is_capability_available(AndroidCapability.CAMERA_READ.value)
        assert avail_cam is False
        assert "R.I.O. capability policy" in reason_cam

        # Re-allow R.I.O. but revoke Android OS permission layer
        pm.set_rio_permission(AndroidCapability.CAMERA_READ.value, True)
        pm.set_os_permission_grant("android.permission.CAMERA", False)
        avail_cam_os, reason_cam_os = pm.is_capability_available(AndroidCapability.CAMERA_READ.value)
        assert avail_cam_os is False
        assert "Missing required system permission" in reason_cam_os


@pytest.mark.asyncio
async def test_android_action_handler_access_levels():
    handler = AndroidActionHandler(device_id="rio-phone-test")

    # Level 1: Application Launch
    act_launch = DeviceAction(
        device_id="rio-phone-test",
        capability="application.launch",
        action_type="android.launch_app",
        parameters={"package": "com.whatsapp"},
    )
    obs_launch = await handler.execute(act_launch)
    assert obs_launch.success is True
    assert obs_launch.data["package"] == "com.whatsapp"
    assert obs_launch.data["state"] == "resumed"
    assert obs_launch.data["access_level"] == AndroidAccessLevel.LEVEL_1_LAUNCH.value
    assert obs_launch.evidence["intent_dispatched"] is True

    # Level 2: Touch Input
    act_touch = DeviceAction(
        device_id="rio-phone-test",
        capability="touch.control",
        action_type="touch.tap",
        parameters={"x": 500, "y": 1000},
    )
    obs_touch = await handler.execute(act_touch)
    assert obs_touch.success is True
    assert obs_touch.data["touch_type"] == "tap"
    assert obs_touch.data["coordinates"] == {"x": 500, "y": 1000}

    # Level 3: Screen Capture
    act_screen = DeviceAction(
        device_id="rio-phone-test",
        capability="screen.read",
        action_type="screen.capture",
    )
    obs_screen = await handler.execute(act_screen)
    assert obs_screen.success is True
    assert "screenshot_path" in obs_screen.data

    # Level 4: Camera Capture
    act_cam = DeviceAction(
        device_id="rio-phone-test",
        capability="camera.read",
        action_type="camera.capture",
        parameters={"facing": "back"},
    )
    obs_cam = await handler.execute(act_cam)
    assert obs_cam.success is True
    assert "photo_uri" in obs_cam.data


@pytest.mark.asyncio
async def test_android_heartbeat_emission():
    emitted = []

    async def mock_send(msg: str):
        emitted.append(json.loads(msg))

    hb = AndroidHeartbeatManager(
        device_id="rio-phone-hb",
        send_fn=mock_send,
        interval_seconds=0.1,
    )
    hb.update_battery_state(78.5, True)
    hb.start()
    await asyncio.sleep(0.25)
    hb.stop()

    assert len(emitted) >= 2
    pkt = emitted[0]
    assert pkt["type"] == "heartbeat"
    assert pkt["device_id"] == "rio-phone-hb"
    assert pkt["platform"] == "android"
    assert pkt["telemetry"]["battery_level"] == 78.5
    assert pkt["telemetry"]["battery_charging"] is True
