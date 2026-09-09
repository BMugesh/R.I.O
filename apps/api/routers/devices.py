"""Devices API Router."""

from typing import Dict, List
from fastapi import APIRouter, Depends
from packages.schemas.devices import Device, DeviceCapability, DeviceStatus, DeviceType
from apps.api.deps import Container, get_container

router = APIRouter(prefix="/devices", tags=["Devices"])

# In-memory device registry
_registered_devices: Dict[str, Device] = {
    "laptop-01": Device(
        device_id="laptop-01",
        name="Primary Work Laptop",
        type=DeviceType.LAPTOP,
        status=DeviceStatus.ONLINE,
        capabilities=[
            DeviceCapability.SCREEN_CAPTURE,
            DeviceCapability.MOUSE_CONTROL,
            DeviceCapability.KEYBOARD_CONTROL,
            DeviceCapability.APP_MANAGEMENT,
            DeviceCapability.BROWSER_CONTROL,
            DeviceCapability.FILESYSTEM,
        ],
        permissions=["all"],
    ),
    "android-01": Device(
        device_id="android-01",
        name="Pixel Phone",
        type=DeviceType.ANDROID,
        status=DeviceStatus.ONLINE,
        capabilities=[
            DeviceCapability.CAMERA,
            DeviceCapability.MICROPHONE,
            DeviceCapability.NOTIFICATIONS,
            DeviceCapability.LOCATION,
            DeviceCapability.SENSORS,
        ],
        permissions=["read_notifications", "camera"],
    ),
}


@router.get("", response_model=List[Device])
async def list_devices():
    """List all registered devices and their capabilities."""
    return list(_registered_devices.values())


@router.post("/register", response_model=Device)
async def register_device(device: Device):
    """Register or update a hardware device agent."""
    _registered_devices[device.device_id] = device
    return device
