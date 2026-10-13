"""End-to-End Multi-Device Integration Tests for R.I.O. (Milestone 2.5 + Android Runtime).

Validates complete paths:
1. CLI -> Core -> Laptop -> ComputerAgent -> Chrome -> Verification
2. Web API -> Core -> Laptop -> VS Code -> Verification
3. CLI -> Core -> Phone -> Android Runtime -> Chrome -> Verification
4. CLI -> Core -> Phone -> Android Runtime -> WhatsApp -> Verification
5. Voice/User Camera Intent -> Router -> Phone -> Camera -> Verification
6. Compound Multi-Device DAG: "Open Chrome on my phone and VS Code on my laptop"
"""
import pytest
pytestmark = pytest.mark.integration



import pytest
from apps.api.deps import container
from packages.schemas.chat import ChatRequest
from packages.schemas.tasks import TaskStatus


@pytest.mark.asyncio
async def test_e2e_scenario_1_laptop_chrome():
    """Scenario 1: CLI -> Core -> Laptop -> ComputerAgent -> Chrome -> Verification."""
    req = ChatRequest(
        message="Open Chrome on my laptop",
        sessionId="test_s1",
        developerMode=True,
    )
    res = await container.orchestrator.process_chat(req)
    assert res.status == "completed"
    assert "Chrome is open" in res.reply
    assert res.developer_trace is not None
    assert len(res.developer_trace.steps) >= 2


@pytest.mark.asyncio
async def test_e2e_scenario_2_web_api_laptop_vscode():
    """Scenario 2: Web UI / API -> Core -> Laptop -> VS Code -> Verification."""
    req = ChatRequest(
        message="Open VS Code on my laptop",
        sessionId="test_s2",
        developerMode=True,
    )
    res = await container.orchestrator.process_chat(req)
    assert res.status == "completed"
    assert "VS Code is open" in res.reply or "Vs Code is open" in res.reply
    assert res.developer_trace is not None


@pytest.mark.asyncio
async def test_e2e_scenario_3_phone_chrome():
    """Scenario 3: CLI -> Core -> Phone -> Android Runtime -> Chrome -> Verification."""
    req = ChatRequest(
        message="Open Chrome on my phone",
        sessionId="test_s3",
        developerMode=True,
    )
    res = await container.orchestrator.process_chat(req)
    assert res.status == "completed"
    assert "Chrome is open on your phone" in res.reply
    assert res.developer_trace is not None
    assert any(s.agent_id == "device_agent" for s in res.developer_trace.steps)


@pytest.mark.asyncio
async def test_e2e_scenario_4_phone_whatsapp():
    """Scenario 4: CLI -> Core -> Phone -> Android Runtime -> WhatsApp -> Verification."""
    req = ChatRequest(
        message="Open WhatsApp on my phone",
        sessionId="test_s4",
        developerMode=True,
    )
    res = await container.orchestrator.process_chat(req)
    assert res.status == "completed"
    assert "WhatsApp is open on your phone" in res.reply or "Whatsapp is open on your phone" in res.reply


@pytest.mark.asyncio
async def test_e2e_scenario_5_camera_capability_routing():
    """Scenario 5: User asks for camera -> Device Router -> Phone -> camera.read -> Android permission -> Camera -> Verification."""
    # Check router capability matching
    route_res = container.device_router.route_action(
        prompt="Take a photo",
        action_type="camera.capture",
        parameters={"facing": "back"},
    )
    assert route_res.target_device is not None
    assert route_res.target_device.platform == "android"

    # Execute chat intent
    req = ChatRequest(
        message="Take a photo",
        sessionId="test_s5",
        developerMode=True,
    )
    res = await container.orchestrator.process_chat(req)
    assert res.status == "completed"
    assert "photo" in res.reply.lower()


@pytest.mark.asyncio
async def test_e2e_scenario_6_multi_device_compound_dag():
    """Scenario 6: Multi-Device DAG task: 'Open Chrome on my phone and VS Code on my laptop'."""
    req = ChatRequest(
        message="Open Chrome on my phone and VS Code on my laptop",
        sessionId="test_s6",
        developerMode=True,
    )
    res = await container.orchestrator.process_chat(req)
    assert res.status == "completed"
    assert "Chrome is open on your phone" in res.reply
    assert "VS Code is open on your laptop" in res.reply or "Vs Code is open on your laptop" in res.reply
    assert res.developer_trace is not None
    # Must have multi-device steps
    agent_ids = [s.agent_id for s in res.developer_trace.steps]
    assert "device_agent" in agent_ids
    assert "computer_agent" in agent_ids
