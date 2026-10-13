"""Comprehensive Unit and Integration Tests for Device Registry."""
import pytest
pytestmark = pytest.mark.unit



import json
from pathlib import Path
import tempfile
import pytest
from packages.schemas.devices import Device, DeviceCapability, DeviceStatus, DeviceType
from services.device_registry.registry import DeviceRegistry


def test_device_registry_initialization_and_seeding():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        reg = DeviceRegistry(persistence_dir=tmp_path, seed_defaults=True)
        devs = reg.list_devices()
        assert len(devs) >= 2

        laptop = reg.get_device("laptop-01")
        assert laptop is not None
        assert laptop.platform == "windows"
        assert laptop.status == DeviceStatus.ONLINE

        phone = reg.get_device("android-01")
        assert phone is not None
        assert phone.platform == "android"


def test_device_registry_persistence_and_reload():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        reg1 = DeviceRegistry(persistence_dir=tmp_path, seed_defaults=False)
        dev = Device(
            device_id="custom-dev-01",
            name="Custom Server",
            type=DeviceType.SERVER,
            platform="linux",
            capabilities=[DeviceCapability.FILESYSTEM_READ],
        )
        reg1.register_device(dev)

        # Reload in a new registry instance on same dir
        reg2 = DeviceRegistry(persistence_dir=tmp_path, seed_defaults=False)
        loaded = reg2.get_device("custom-dev-01")
        assert loaded is not None
        assert loaded.name == "Custom Server"
        assert loaded.platform == "linux"
        assert loaded.status == DeviceStatus.ONLINE


def test_device_registry_disconnect_and_reconnect():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        reg = DeviceRegistry(persistence_dir=tmp_path, seed_defaults=True)

        reg.disconnect_device("laptop-01")
        dev = reg.get_device("laptop-01")
        assert dev.status == DeviceStatus.OFFLINE
        assert dev.connection_state == "offline"

        reg.reconnect_device("laptop-01")
        dev2 = reg.get_device("laptop-01")
        assert dev2.status == DeviceStatus.ONLINE
        assert dev2.connection_state == "online"


def test_device_registry_heartbeat():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        reg = DeviceRegistry(persistence_dir=tmp_path, seed_defaults=True)

        hb_res = reg.record_heartbeat("android-01", metadata={"battery": 92.0})
        assert hb_res is True
        dev = reg.get_device("android-01")
        assert dev.metadata.get("battery") == 92.0

        # Heartbeat for non-existent device returns False
        assert reg.record_heartbeat("non-existent-device") is False


def test_device_registry_capability_and_platform_lookup():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        reg = DeviceRegistry(persistence_dir=tmp_path, seed_defaults=True)

        # Find camera capable devices
        cam_devs = reg.get_devices_with_capability("camera.read")
        assert len(cam_devs) >= 1
        assert cam_devs[0].platform == "android"

        # Find mouse capable devices
        mouse_devs = reg.get_devices_with_capability("mouse.control")
        assert len(mouse_devs) >= 1
        assert mouse_devs[0].platform == "windows"

        # Platform lookup
        androids = reg.get_devices_by_platform("android")
        assert len(androids) >= 1

        windows_devs = reg.get_devices_by_platform("windows")
        assert len(windows_devs) >= 1


def test_device_registry_unregister():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        reg = DeviceRegistry(persistence_dir=tmp_path, seed_defaults=True)

        assert reg.get_device("laptop-01") is not None
        removed = reg.unregister_device("laptop-01")
        assert removed is True
        assert reg.get_device("laptop-01") is None
        assert reg.unregister_device("laptop-01") is False
