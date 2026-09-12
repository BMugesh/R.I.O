"""Comprehensive Test Suite for Origin Device Binding & Local Execution in R.I.O.

Validates the core R.I.O. principle:
"ONE BRAIN — LOCAL BODY BY DEFAULT — REMOTE BODY ONLY WHEN EXPLICITLY REQUESTED"

Test Matrix:
1. Phone Origin Defaults to Phone Without Asking
2. Laptop Origin Defaults to Laptop Without Asking
3. CLI Origin Defaults to Local Workstation Without Asking
4. Explicit Remote Overrides (Phone -> Laptop, Laptop -> Phone)
5. Missing Capability Safety Protection (No Silent Redirection)
6. Device Router 5-Tier Priority Matrix
7. Security Boundary Enforcement
"""

from pathlib import Path
import tempfile
import pytest
from apps.api.deps import container
from packages.schemas.chat import ChatRequest
from packages.schemas.devices import (
    Device,
    DeviceCapability,
    DeviceResolution,
    DeviceStatus,
    DeviceType,
    InterfaceType,
    OriginContext,
)
from services.device_registry.registry import DeviceRegistry
from services.device_router.router import DeviceRouter


# ============================================================================
# 1. Device Router 5-Tier Resolution Unit Tests
# ============================================================================

def test_router_origin_device_binding_phone():
    """Origin phone context binds default execution to phone without ambiguity."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        reg = DeviceRegistry(persistence_dir=Path(tmp_dir), seed_defaults=True)
        router = DeviceRouter(registry=reg)

        origin_phone = OriginContext(
            session_id="phone_sess_1",
            interface_type=InterfaceType.ANDROID,
            origin_device_id="phone-01",
            origin_platform="android",
        )

        res = router.route_action(
            prompt="Open WhatsApp",
            action_type="application.launch",
            parameters={"app_name": "WhatsApp"},
            origin_context=origin_phone,
        )

        assert res.target_device is not None
        assert res.target_device.device_id in ("phone-01", "android-01")
        assert res.target_device.platform == "android"
        assert res.is_ambiguous is False
        assert res.explicit_override is False
        assert res.resolution_reason == "origin_device_binding"



def test_router_origin_device_binding_laptop():
    """Origin laptop context binds default execution to laptop without ambiguity."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        reg = DeviceRegistry(persistence_dir=Path(tmp_dir), seed_defaults=True)
        router = DeviceRouter(registry=reg)

        origin_laptop = OriginContext(
            session_id="laptop_sess_1",
            interface_type=InterfaceType.CLI,
            origin_device_id="laptop-01",
            origin_platform="windows",
        )

        res = router.route_action(
            prompt="Open WhatsApp",
            action_type="application.launch",
            parameters={"app_name": "WhatsApp"},
            origin_context=origin_laptop,
        )

        assert res.target_device is not None
        assert res.target_device.device_id == "laptop-01"
        assert res.target_device.platform == "windows"
        assert res.is_ambiguous is False
        assert res.explicit_override is False
        assert res.resolution_reason == "origin_device_binding"


def test_router_explicit_remote_override_from_phone():
    """Explicit 'on my laptop' overrides origin phone context."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        reg = DeviceRegistry(persistence_dir=Path(tmp_dir), seed_defaults=True)
        router = DeviceRouter(registry=reg)

        origin_phone = OriginContext(
            session_id="phone_sess_2",
            interface_type=InterfaceType.ANDROID,
            origin_device_id="phone-01",
            origin_platform="android",
        )

        res = router.route_action(
            prompt="Open VS Code on my laptop",
            action_type="application.launch",
            parameters={"app_name": "VS Code"},
            origin_context=origin_phone,
        )

        assert res.target_device is not None
        assert res.target_device.device_id == "laptop-01"
        assert res.target_device.platform == "windows"
        assert res.explicit_override is True
        assert res.resolution_reason == "explicit_user_target"


def test_router_explicit_remote_override_from_laptop():
    """Explicit 'on my phone' overrides origin laptop context."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        reg = DeviceRegistry(persistence_dir=Path(tmp_dir), seed_defaults=True)
        router = DeviceRouter(registry=reg)

        origin_laptop = OriginContext(
            session_id="laptop_sess_2",
            interface_type=InterfaceType.DESKTOP,
            origin_device_id="laptop-01",
            origin_platform="windows",
        )

        res = router.route_action(
            prompt="Open WhatsApp on my phone",
            action_type="application.launch",
            parameters={"app_name": "WhatsApp"},
            origin_context=origin_laptop,
        )

        assert res.target_device is not None
        assert res.target_device.device_id in ("phone-01", "android-01")
        assert res.target_device.platform == "android"
        assert res.explicit_override is True
        assert res.resolution_reason == "explicit_user_target"



def test_router_missing_origin_capability_fails_safely():
    """Origin device lacking required capability does NOT silently redirect."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        reg = DeviceRegistry(persistence_dir=Path(tmp_dir), seed_defaults=False)
        # Register a device with only application launch capability (no camera)
        reg.register_device(Device(
            device_id="kiosk-01",
            name="Info Kiosk",
            type=DeviceType.DESKTOP,
            platform="windows",
            status=DeviceStatus.ONLINE,
            capabilities=[DeviceCapability.APPLICATION_LAUNCH],
        ))
        # Register phone with camera
        reg.register_device(Device(
            device_id="phone-01",
            name="Pixel Phone",
            type=DeviceType.ANDROID,
            platform="android",
            status=DeviceStatus.ONLINE,
            capabilities=[DeviceCapability.APPLICATION_LAUNCH, DeviceCapability.CAMERA_READ],
        ))

        router = DeviceRouter(registry=reg)

        origin_kiosk = OriginContext(
            session_id="kiosk_sess",
            interface_type=InterfaceType.DESKTOP,
            origin_device_id="kiosk-01",
        )

        # Kiosk attempts camera capture without explicit remote target
        res = router.route_action(
            prompt="Take a photo",
            action_type="camera.capture",
            parameters={"facing": "back"},
            origin_context=origin_kiosk,
        )

        # Must fail safely on origin kiosk rather than silently capturing photo on phone-01
        assert res.target_device is None
        assert res.action is None
        assert res.error is not None
        assert "does not support required capability" in res.error
        assert res.resolution_reason == "origin_capability_missing"


# ============================================================================
# 2. End-to-End Orchestrator Origin Binding Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_e2e_phone_origin_opens_whatsapp_locally():
    """Phone origin -> 'Open WhatsApp' -> executes locally on phone without asking 'which device?'."""
    req = ChatRequest(
        message="Open WhatsApp",
        sessionId="mobile_session_101",
        interfaceType="android",
        originDeviceId="phone-01",
        developerMode=True,
    )
    res = await container.orchestrator.process_chat(req)

    assert res.status == "completed"
    assert "WhatsApp is open" in res.reply or "Whatsapp is open" in res.reply
    assert "on your phone" not in res.reply  # Local execution doesn't need redundant remote qualifier
    assert res.developer_trace is not None
    assert res.developer_trace.origin_device_id in ("phone-01", "android-01")
    assert res.developer_trace.execution_device_id in ("phone-01", "android-01")
    assert res.developer_trace.explicit_override is False
    assert any(s.agent_id == "device_agent" for s in res.developer_trace.steps)


@pytest.mark.asyncio
async def test_e2e_laptop_origin_opens_whatsapp_locally():
    """Laptop origin -> 'Open WhatsApp' -> executes locally on laptop without asking 'which device?'."""
    req = ChatRequest(
        message="Open WhatsApp",
        sessionId="desktop_session_101",
        interfaceType="desktop",
        originDeviceId="laptop-01",
        developerMode=True,
    )
    res = await container.orchestrator.process_chat(req)

    assert res.status == "completed"
    assert "WhatsApp is open" in res.reply or "Whatsapp is open" in res.reply
    assert res.developer_trace is not None
    assert res.developer_trace.origin_device_id in ("laptop-01", "desktop-01")
    assert res.developer_trace.execution_device_id in ("laptop-01", "desktop-01")
    assert res.developer_trace.explicit_override is False
    assert any(s.agent_id == "computer_agent" for s in res.developer_trace.steps)


@pytest.mark.asyncio
async def test_e2e_cli_origin_opens_chrome_locally():
    """CLI origin -> 'Open Chrome' -> executes locally on laptop/workstation."""
    req = ChatRequest(
        message="Open Chrome",
        sessionId="cli_session_101",
        interfaceType="cli",
        originDeviceId="laptop-01",
        developerMode=True,
    )
    res = await container.orchestrator.process_chat(req)

    assert res.status == "completed"
    assert "Chrome is open" in res.reply
    assert res.developer_trace is not None
    assert res.developer_trace.origin_device_id in ("laptop-01", "desktop-01")
    assert res.developer_trace.execution_device_id in ("laptop-01", "desktop-01")
    assert res.developer_trace.explicit_override is False


@pytest.mark.asyncio
async def test_e2e_phone_origin_explicit_laptop_override():
    """Phone origin -> 'Open VS Code on my laptop' -> routes remotely to laptop."""
    req = ChatRequest(
        message="Open VS Code on my laptop",
        sessionId="mobile_session_102",
        interfaceType="android",
        originDeviceId="phone-01",
        developerMode=True,
    )
    res = await container.orchestrator.process_chat(req)

    assert res.status == "completed"
    assert "VS Code is open on your laptop" in res.reply or "Vs Code is open on your laptop" in res.reply
    assert res.developer_trace is not None
    assert res.developer_trace.origin_device_id in ("phone-01", "android-01")
    assert res.developer_trace.execution_device_id in ("laptop-01", "desktop-01")
    assert res.developer_trace.explicit_override is True
    assert any(s.agent_id == "computer_agent" for s in res.developer_trace.steps)



@pytest.mark.asyncio
async def test_e2e_phone_origin_missing_capability_safe_rejection():
    """Phone origin -> 'Open VS Code' (no laptop mentioned) -> fails safely with clear diagnostic without silent redirect."""
    req = ChatRequest(
        message="Open VS Code",
        sessionId="mobile_session_103",
        interfaceType="android",
        originDeviceId="phone-01",
        developerMode=True,
    )
    res = await container.orchestrator.process_chat(req)

    assert res.status == "failed"
    assert "does not support desktop application" in res.reply
    assert "on my laptop" in res.reply
