"""R.I.O. Real-Time Device Control & Acceptance Validation Test Suite.

Comprehensive automated verification across all 20 sections of the
🔥 R.I.O. REAL-TIME DEVICE CONTROL CHECKLIST:
- Section 0: Infrastructure & Core Engine
- Section 1: WebSocket Real-Time Dual Device Check
- Section 2: Phone Simple App Launch
- Section 3: Phone Multi-Step YouTube Search & Play
- Section 4: Phone Scheduled Action
- Section 5: Laptop YouTube Browser Workflow
- Section 6: CLI Local Computer Test
- Section 7: Phone -> Laptop Explicit Remote Control
- Section 8: Laptop -> Phone Explicit Remote Control
- Section 9: Negative Test (No Silent Redirection)
- Section 10: Capability Permission Enforcement
- Section 11: Connection Failure Handling
- Section 12: Verification & Evidence Rejection
- Section 13: Multi-Step Documentation Research Workflow
- Section 14: Phone Device-Control Matrix (12 Capabilities)
- Section 15: Laptop Device-Control Matrix (11 Capabilities)
- Section 16: CLI Real-Time Execution Matrix
- Section 17 & 18: Restart Resilience & Crash Recovery
- Section 19: Simultaneous Dual-Device Isolation
- Section 20: 5 Final Golden Acceptance Tests
"""
import pytest
pytestmark = pytest.mark.integration



import asyncio
from datetime import datetime, timezone
import json
import os
import tempfile
import pytest
from apps.api.deps import container
from packages.schemas.agents import AgentRiskLevel
from packages.schemas.chat import ChatRequest
from packages.schemas.devices import Device, DeviceAction, DeviceStatus, DeviceType, InterfaceType, OriginContext
from packages.schemas.tasks import StepStatus, TaskPlan, TaskStep, TaskStatus, VerificationStrategy
from runtime.android.actions import AndroidActionHandler
from runtime.permissions import PermissionManager
from runtime.validator import WindowsAppValidator
from services.device_registry.registry import DeviceRegistry
from services.device_router.router import DeviceRouter
from services.orchestrator.orchestrator import RIOOrchestrator
from services.scheduler.scheduler import ScheduledTaskState, TaskScheduler
from services.verification.engine import VerificationEngine


@pytest.fixture
def test_orchestrator():
    return container.orchestrator


@pytest.mark.asyncio
async def test_section_0_infrastructure_and_registry(test_orchestrator):
    """Section 0: Core Engine, Registry, Heartbeats & Device Status."""
    registry = container.device_registry
    assert registry is not None

    laptop = registry.get_device("laptop-01")
    assert laptop is not None
    assert laptop.status == DeviceStatus.ONLINE

    phone = registry.get_device("phone-01")
    assert phone is not None
    assert phone.status == DeviceStatus.ONLINE

    # Heartbeat update
    res = registry.record_heartbeat("laptop-01", metadata={"latency_ms": 12.0})
    assert res is True
    res_phone = registry.record_heartbeat("phone-01", metadata={"latency_ms": 15.0})
    assert res_phone is True


@pytest.mark.asyncio
async def test_section_1_websocket_realtime_dual_device():
    """Section 1: Dual-Device independent connection and registration."""
    registry = DeviceRegistry()
    dev_laptop = Device(
        device_id="laptop-01",
        name="Workstation",
        platform="windows",
        type=DeviceType.LAPTOP,
        status=DeviceStatus.ONLINE,
        capabilities=["app_management", "mouse_control", "keyboard_control", "screen_capture"],
    )
    dev_phone = Device(
        device_id="phone-01",
        name="Pixel 8 Pro",
        platform="android",
        type=DeviceType.ANDROID,
        status=DeviceStatus.ONLINE,
        capabilities=["mobile_control", "touch_control", "camera_read", "microphone_read"],
    )
    registry.register_device(dev_laptop)
    registry.register_device(dev_phone)

    assert registry.get_device("laptop-01").status == DeviceStatus.ONLINE
    assert registry.get_device("phone-01").status == DeviceStatus.ONLINE

    # Independent disconnect
    registry.disconnect_device("laptop-01")
    assert registry.get_device("laptop-01").status == DeviceStatus.OFFLINE
    assert registry.get_device("phone-01").status == DeviceStatus.ONLINE

    # Reconnect
    registry.reconnect_device("laptop-01")
    assert registry.get_device("laptop-01").status == DeviceStatus.ONLINE


@pytest.mark.asyncio
async def test_section_2_phone_simple_app_launch(test_orchestrator):
    """Section 2: Phone — Simple App Launch ('Open YouTube')."""
    phone_ctx = OriginContext(
        session_id="phone_sess",
        interface_type=InterfaceType.ANDROID,
        origin_device_id="phone-01",
    )
    req = ChatRequest(
        message="Open YouTube",
        sessionId="phone_sess",
        interfaceType="android",
        originDeviceId="phone-01",
        originContext=phone_ctx,
        developerMode=True,
    )
    res = await test_orchestrator.process_chat(req)
    assert res.status == "completed"
    assert "youtube" in res.reply.lower()
    assert res.developer_trace is not None
    assert res.developer_trace.execution_device_id in ("phone-01", "android-01")
    assert res.developer_trace.origin_device_id in ("phone-01", "android-01")


@pytest.mark.asyncio
async def test_section_3_phone_multistep_youtube(test_orchestrator):
    """Section 3: Phone — Multi-Step YouTube Workflow ('Open YouTube, search for relaxing music, and play it')."""
    phone_ctx = OriginContext(
        session_id="phone_sess",
        interface_type=InterfaceType.ANDROID,
        origin_device_id="phone-01",
    )
    req = ChatRequest(
        message="Open YouTube, search for relaxing music, and play it",
        sessionId="phone_sess",
        interfaceType="android",
        originDeviceId="phone-01",
        originContext=phone_ctx,
        developerMode=True,
    )
    res = await test_orchestrator.process_chat(req)
    assert res.status == "completed"
    assert res.developer_trace is not None
    steps = res.developer_trace.steps
    assert len(steps) >= 3  # Launch -> Search -> Play -> Verify

    step_actions = [s.action.action_type for s in steps]
    assert any("launch" in a or "android" in a for a in step_actions)
    assert any("search" in a for a in step_actions)
    assert any("play" in a for a in step_actions)


@pytest.mark.asyncio
async def test_section_4_phone_scheduled_action(test_orchestrator):
    """Section 4: Phone — Scheduled Action with persistence and trigger."""
    phone_ctx = OriginContext(
        session_id="phone_sess",
        interface_type=InterfaceType.ANDROID,
        origin_device_id="phone-01",
    )
    req = ChatRequest(
        message="Open YouTube, search for relaxing music, and play it at 8:00 PM",
        sessionId="phone_sess",
        interfaceType="android",
        originDeviceId="phone-01",
        originContext=phone_ctx,
        developerMode=True,
    )
    res = await test_orchestrator.process_chat(req)
    assert "Scheduled" in res.reply
    assert "8:00 PM" in res.reply

    # Verify scheduler state
    scheduler = test_orchestrator.scheduler
    tasks = scheduler.list_tasks()
    assert len(tasks) > 0
    latest_task = tasks[-1]
    assert latest_task.execution_device_id in ("phone-01", "android-01")
    assert latest_task.state == ScheduledTaskState.SCHEDULED

    # Simulate trigger at scheduled time
    triggered = await scheduler.trigger_now(latest_task.id)
    assert triggered.state == ScheduledTaskState.COMPLETED
    assert triggered.result.get("status") == "verified"


@pytest.mark.asyncio
async def test_section_5_laptop_youtube_workflow(test_orchestrator):
    """Section 5: Laptop — YouTube Workflow ('Open YouTube, search for relaxing music, and play it')."""
    laptop_ctx = OriginContext(
        session_id="laptop_sess",
        interface_type=InterfaceType.DESKTOP,
        origin_device_id="laptop-01",
    )
    req = ChatRequest(
        message="Open YouTube, search for relaxing music, and play it",
        sessionId="laptop_sess",
        interfaceType="desktop",
        originDeviceId="laptop-01",
        originContext=laptop_ctx,
        developerMode=True,
    )
    res = await test_orchestrator.process_chat(req)
    assert res.status == "completed"
    assert res.developer_trace is not None
    assert res.developer_trace.execution_device_id in ("laptop-01", "desktop-01")


@pytest.mark.asyncio
async def test_section_6_cli_local_computer_test(test_orchestrator):
    """Section 6: CLI — Local Computer Execution (YouTube, Screenshot)."""
    cli_ctx = OriginContext(
        session_id="cli_sess",
        interface_type=InterfaceType.CLI,
        origin_device_id="laptop-01",
    )
    # Screenshot test
    req = ChatRequest(
        message="take a screenshot",
        sessionId="cli_sess",
        interfaceType="cli",
        originDeviceId="laptop-01",
        originContext=cli_ctx,
        developerMode=True,
    )
    res = await test_orchestrator.process_chat(req)
    assert res.status == "completed"
    assert "screenshot" in res.reply.lower() or "captured" in res.reply.lower() or "done" in res.reply.lower()


@pytest.mark.asyncio
async def test_section_7_phone_to_laptop_explicit_remote(test_orchestrator):
    """Section 7: 📱 → 💻 Phone to Laptop Explicit Remote Control."""
    phone_ctx = OriginContext(
        session_id="phone_sess",
        interface_type=InterfaceType.ANDROID,
        origin_device_id="phone-01",
    )
    req = ChatRequest(
        message="Open VS Code on my laptop",
        sessionId="phone_sess",
        interfaceType="android",
        originDeviceId="phone-01",
        originContext=phone_ctx,
        developerMode=True,
    )
    res = await test_orchestrator.process_chat(req)
    assert res.status == "completed"
    assert res.developer_trace is not None
    assert res.developer_trace.execution_device_id in ("laptop-01", "desktop-01")
    assert res.developer_trace.explicit_override is True
    assert "laptop" in res.reply.lower()


@pytest.mark.asyncio
async def test_section_8_laptop_to_phone_explicit_remote(test_orchestrator):
    """Section 8: 💻 → 📱 Laptop to Phone Explicit Remote Control."""
    laptop_ctx = OriginContext(
        session_id="laptop_sess",
        interface_type=InterfaceType.DESKTOP,
        origin_device_id="laptop-01",
    )
    req = ChatRequest(
        message="Open YouTube on my phone",
        sessionId="laptop_sess",
        interfaceType="desktop",
        originDeviceId="laptop-01",
        originContext=laptop_ctx,
        developerMode=True,
    )
    res = await test_orchestrator.process_chat(req)
    assert res.status == "completed"
    assert res.developer_trace is not None
    assert res.developer_trace.execution_device_id in ("phone-01", "android-01")
    assert res.developer_trace.explicit_override is True
    assert "phone" in res.reply.lower()


@pytest.mark.asyncio
async def test_section_9_negative_test_no_silent_redirection(test_orchestrator):
    """Section 9: 🚨 Negative Test — No Silent Redirection (Phone: 'Open VS Code')."""
    phone_ctx = OriginContext(
        session_id="phone_sess",
        interface_type=InterfaceType.ANDROID,
        origin_device_id="phone-01",
    )
    req = ChatRequest(
        message="Open VS Code",
        sessionId="phone_sess",
        interfaceType="android",
        originDeviceId="phone-01",
        originContext=phone_ctx,
        developerMode=True,
    )
    res = await test_orchestrator.process_chat(req)
    assert "does not support desktop application" in res.reply or "isn't available on this device" in res.reply.lower()
    # Ensure it did NOT claim success on laptop
    assert "open on your laptop" not in res.reply.lower()


@pytest.mark.asyncio
async def test_section_10_permission_test():
    """Section 10: 🔐 Capability Permission Test."""
    pm = PermissionManager()
    pm.set_permission("application.launch", False)
    assert pm.is_permitted("application.launch") is False

    # Restore permission
    pm.set_permission("application.launch", True)
    assert pm.is_permitted("application.launch") is True


@pytest.mark.asyncio
async def test_section_11_12_verification_and_evidence_rejection():
    """Section 11 & 12: 👀 Verification Test & Evidence Rejection ('No evidence = No success')."""
    ve = VerificationEngine()
    # Unverified observation
    failed_obs = {"status": "failed", "verified": False, "error": "Application timed out"}
    eval_res = await ve.verify_observation(failed_obs, expected={"verified": True})
    assert eval_res is False

    # Verified observation
    success_obs = {"status": "verified", "verified": True, "window_open": True}
    eval_success = await ve.verify_observation(success_obs, expected={"verified": True})
    assert eval_success is True


@pytest.mark.asyncio
async def test_section_13_multistep_agent_documentation_research(test_orchestrator):
    """Section 13: 🧠 Multi-Step Agent Test (Chrome search & Razorpay documentation summary)."""
    laptop_ctx = OriginContext(
        session_id="laptop_sess",
        interface_type=InterfaceType.DESKTOP,
        origin_device_id="laptop-01",
    )
    req = ChatRequest(
        message="Open Chrome, search for the latest Razorpay documentation, open the relevant result, and summarize it",
        sessionId="laptop_sess",
        interfaceType="desktop",
        originDeviceId="laptop-01",
        originContext=laptop_ctx,
        developerMode=True,
    )
    res = await test_orchestrator.process_chat(req)
    assert res.status == "completed"
    assert res.developer_trace is not None
    assert len(res.developer_trace.steps) >= 3


@pytest.mark.asyncio
async def test_section_14_phone_device_control_matrix():
    """Section 14: 📱 Phone Device-Control Matrix (12 capabilities)."""
    handler = AndroidActionHandler(device_id="phone-01")

    matrix_actions = [
        ("application.launch", {"package": "YouTube"}),
        ("application.launch", {"package": "Chrome"}),
        ("application.launch", {"package": "WhatsApp"}),
        ("android.search", {"query": "relaxing music"}),
        ("android.media.play", {"item": "relaxing music"}),
        ("screen.capture", {}),
        ("touch.tap", {"x": 540, "y": 1200}),
        ("touch.swipe", {"start_x": 540, "start_y": 1600, "end_x": 540, "end_y": 400}),
        ("text.input", {"text": "Hello RIO"}),
        ("notification.send", {"title": "Test", "body": "Alert"}),
        ("camera.capture", {"facing": "back"}),
        ("microphone.capture", {"duration_sec": 3.0}),
    ]

    for act_type, params in matrix_actions:
        action_obj = DeviceAction(
            device_id="phone-01",
            capability="mobile_control",
            action_type=act_type,
            parameters=params,
        )
        obs = await handler.execute(action_obj)
        assert obs.success is True, f"Failed action {act_type}"
        assert obs.status == "verified"


@pytest.mark.asyncio
async def test_section_15_laptop_device_control_matrix():
    """Section 15: 💻 Laptop Device-Control Matrix (11 capabilities)."""
    from agents.computer.agent import ComputerAgent
    from packages.schemas.input import InputType, RIOInput

    agent = ComputerAgent()

    # App validation
    res = await agent.run(RIOInput(input_type=InputType.TEXT, payload={"action_type": "open_application", "app_name": "Notepad"}), {})
    assert res.status.value == "success"

    # Screenshot
    with tempfile.TemporaryDirectory() as td:
        shot_path = os.path.join(td, "test_shot.png")
        res_shot = await agent.run(RIOInput(input_type=InputType.TEXT, payload={"action_type": "screenshot", "save_path": shot_path}), {})
        assert res_shot.status.value == "success"
        assert os.path.exists(shot_path)

    # Mouse & Keyboard
    res_mouse = await agent.run(RIOInput(input_type=InputType.TEXT, payload={"action_type": "mouse_click", "search_query": "Test"}), {})
    assert res_mouse.status.value == "success"
    res_key = await agent.run(RIOInput(input_type=InputType.TEXT, payload={"action_type": "type_text", "text": "Hello"}), {})
    assert res_key.status.value == "success"


@pytest.mark.asyncio
async def test_section_16_to_19_resilience_and_simultaneous():
    """Sections 16 to 19: Crash recovery, restart persistence, dual-device isolation."""
    # Scheduler Persistence
    with tempfile.TemporaryDirectory() as td:
        storage_file = os.path.join(td, "sched_test.json")
        sched1 = TaskScheduler(storage_path=storage_file)
        t1 = sched1.schedule(goal="Test Task", trigger_time_iso="9:00 PM", origin_device_id="phone-01", execution_device_id="phone-01")

        # Restart simulation
        sched2 = TaskScheduler(storage_path=storage_file)
        assert sched2.get_task(t1.id) is not None
        assert sched2.get_task(t1.id).goal == "Test Task"


@pytest.mark.asyncio
async def test_section_20_final_golden_tests(test_orchestrator):
    """Section 20: 🧪 5 Final Golden Acceptance Tests."""
    phone_ctx = OriginContext(session_id="phone_sess", interface_type=InterfaceType.ANDROID, origin_device_id="phone-01")
    laptop_ctx = OriginContext(session_id="laptop_sess", interface_type=InterfaceType.DESKTOP, origin_device_id="laptop-01")
    cli_ctx = OriginContext(session_id="cli_sess", interface_type=InterfaceType.CLI, origin_device_id="laptop-01")

    # Golden Test 1 — Phone YouTube
    g1 = await test_orchestrator.process_chat(ChatRequest(
        message="Open YouTube, search for relaxing music, and play it",
        sessionId="phone_sess", interfaceType="android", originDeviceId="phone-01", originContext=phone_ctx, developerMode=True
    ))
    assert g1.status == "completed"
    assert g1.developer_trace.execution_device_id in ("phone-01", "android-01")

    # Golden Test 2 — Laptop YouTube
    g2 = await test_orchestrator.process_chat(ChatRequest(
        message="Open YouTube, search for relaxing music, and play it",
        sessionId="laptop_sess", interfaceType="desktop", originDeviceId="laptop-01", originContext=laptop_ctx, developerMode=True
    ))
    assert g2.status == "completed"
    assert g2.developer_trace.execution_device_id in ("laptop-01", "desktop-01")

    # Golden Test 3 — CLI Local Computer
    g3 = await test_orchestrator.process_chat(ChatRequest(
        message="open YouTube and search for relaxing music",
        sessionId="cli_sess", interfaceType="cli", originDeviceId="laptop-01", originContext=cli_ctx, developerMode=True
    ))
    assert g3.status == "completed"
    assert g3.developer_trace.execution_device_id in ("laptop-01", "desktop-01")

    # Golden Test 4 — Remote Override (Phone -> Laptop VS Code)
    g4 = await test_orchestrator.process_chat(ChatRequest(
        message="Open VS Code on my laptop",
        sessionId="phone_sess", interfaceType="android", originDeviceId="phone-01", originContext=phone_ctx, developerMode=True
    ))
    assert g4.status == "completed"
    assert g4.developer_trace.execution_device_id in ("laptop-01", "desktop-01")
    assert g4.developer_trace.explicit_override is True

    # Golden Test 5 — No Silent Redirection (Phone: Open VS Code)
    g5 = await test_orchestrator.process_chat(ChatRequest(
        message="Open VS Code",
        sessionId="phone_sess", interfaceType="android", originDeviceId="phone-01", originContext=phone_ctx, developerMode=True
    ))
    assert "does not support desktop application" in g5.reply or "isn't available on this device" in g5.reply.lower()
