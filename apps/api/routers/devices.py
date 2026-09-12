"""Devices API Router."""

from typing import Dict, List, Optional
from fastapi import APIRouter, Depends
from packages.schemas.devices import Device, DeviceCapability, DeviceStatus, DeviceType
from apps.api.deps import Container, container, get_container

router = APIRouter(prefix="/devices", tags=["Devices"])

# Expose mapping property for backward compatibility with existing tests
_registered_devices = container.device_registry._devices


@router.get("", response_model=List[Device])
async def list_devices(
    status: Optional[DeviceStatus] = None,
    platform: Optional[str] = None,
    cont: Container = Depends(get_container),
):
    """List all registered devices and their capabilities."""
    devs = cont.device_registry.list_devices(filter_status=status)
    if platform:
        devs = [d for d in devs if platform.lower() in (d.platform or "").lower()]
    return devs


@router.get("/{device_id}", response_model=Optional[Device])
async def get_device(
    device_id: str,
    cont: Container = Depends(get_container),
):
    """Get a specific registered device by ID."""
    return cont.device_registry.get_device(device_id)


@router.post("/register", response_model=Device)
async def register_device(
    device: Device,
    cont: Container = Depends(get_container),
):
    """Register or update a hardware device agent."""
    return cont.device_registry.register_device(device)


@router.delete("/{device_id}")
async def unregister_device(
    device_id: str,
    cont: Container = Depends(get_container),
):
    """Unregister a device."""
    removed = cont.device_registry.unregister_device(device_id)
    return {"device_id": device_id, "unregistered": removed}

