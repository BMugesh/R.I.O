"""Comprehensive Unit and Integration Tests for Device Router."""
import pytest
pytestmark = pytest.mark.unit



from pathlib import Path
import tempfile
import pytest
from packages.schemas.devices import Device, DeviceCapability, DeviceStatus, DeviceType
from services.device_registry.registry import DeviceRegistry
from services.device_router.router import DeviceRouter


def test_device_router_explicit_intent_routing():
    with tempfile.TemporaryDirectory() as tmp_dir:
        reg = DeviceRegistry(persistence_dir=Path(tmp_dir), seed_defaults=True)
        router = DeviceRouter(registry=reg)

        # 1. Routing to phone
        res_phone = router.route_action(
            prompt="Open WhatsApp on my phone",
            action_type="application.launch",
            parameters={"app_name": "WhatsApp"},
        )
        assert res_phone.target_device is not None
        assert res_phone.target_device.platform == "android"
        assert res_phone.action is not None
        assert res_phone.action.capability == "application.launch"
        assert res_phone.action.device_id == res_phone.target_device.device_id

        # 2. Routing to laptop
        res_laptop = router.route_action(
            prompt="Open VS Code on my laptop",
            action_type="application.launch",
            parameters={"app_name": "VS Code"},
        )
        assert res_laptop.target_device is not None
        assert res_laptop.target_device.platform == "windows"
        assert res_laptop.action.device_id == res_laptop.target_device.device_id


def test_device_router_capability_exclusive_routing():
    with tempfile.TemporaryDirectory() as tmp_dir:
        reg = DeviceRegistry(persistence_dir=Path(tmp_dir), seed_defaults=True)
        router = DeviceRouter(registry=reg)

        # Camera action without mentioning device should route to camera-capable device (phone)
        res_camera = router.route_action(
            prompt="Take a photo of the whiteboard",
            action_type="camera.capture",
            parameters={"facing": "back"},
        )
        assert res_camera.target_device is not None
        assert res_camera.target_device.platform == "android"

        # Mouse click without mentioning device should route to mouse-capable device (laptop)
        res_mouse = router.route_action(
            prompt="Click on search bar",
            action_type="mouse.click",
            parameters={"coordinates": {"x": 100, "y": 200}},
        )
        assert res_mouse.target_device is not None
        assert res_mouse.target_device.platform == "windows"


def test_device_router_ambiguity_detection():
    with tempfile.TemporaryDirectory() as tmp_dir:
        reg = DeviceRegistry(persistence_dir=Path(tmp_dir), seed_defaults=True)
        router = DeviceRouter(registry=reg)

        # Both laptop and phone support application.launch and both are ONLINE
        res_ambiguous = router.route_action(
            prompt="Open Chrome",
            action_type="application.launch",
            parameters={"app_name": "Chrome"},
        )
        assert res_ambiguous.is_ambiguous is True
        assert "Do you want to run this on" in res_ambiguous.ambiguity_message


def test_device_router_security_boundary_enforcement():
    with tempfile.TemporaryDirectory() as tmp_dir:
        reg = DeviceRegistry(persistence_dir=Path(tmp_dir), seed_defaults=True)
        router = DeviceRouter(registry=reg)

        # Attempt A: Remote eval
        res1 = router.route_action(
            prompt="Run eval(print(1))",
            action_type="eval",
            parameters={"code": "eval('1+1')"},
        )
        assert res1.error is not None
        assert "Security Violation" in res1.error
        assert res1.action is None

        # Attempt B: os.system injection in parameters
        res2 = router.route_action(
            prompt="Run system command",
            action_type="application.launch",
            parameters={"command": "os.system('calc.exe')"},
        )
        assert res2.error is not None
        assert "Security Violation" in res2.error
        assert res2.action is None
