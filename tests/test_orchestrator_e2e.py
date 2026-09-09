"""End-to-End integration tests for R.I.O. Orchestrator and full OS pipelines."""

import pytest
from apps.api.deps import Container
from packages.schemas.chat import ChatRequest
from packages.schemas.safety import ApprovalDecision, ApprovalStatus
from packages.schemas.tasks import TaskStatus


@pytest.mark.asyncio
async def test_e2e_conversational_flow():
    container = Container()
    # Use mock provider for testing
    container.model_router.default_provider = "mock"

    req = ChatRequest(
        message="Hi RIO, how are you?",
        sessionId="session_e2e_01",
        developerMode=False,
    )
    response = await container.orchestrator.process_chat(req)

    assert response.reply != ""
    assert "{" not in response.reply  # Must not leak internal JSON
    assert response.developer_trace is None  # Must be hidden when developerMode is False


@pytest.mark.asyncio
async def test_e2e_whatsapp_action_and_verification_flow():
    container = Container()
    container.model_router.default_provider = "mock"

    req = ChatRequest(
        message="RIO, open WhatsApp and send 'I'll call you tonight' to Arun.",
        sessionId="session_e2e_02",
        developerMode=True,
    )
    response = await container.orchestrator.process_chat(req)

    assert response.status == "completed"
    assert "Done" in response.reply
    assert "Arun" in response.reply or "WhatsApp" in response.reply

    # Developer trace assertions
    assert response.developer_trace is not None
    assert len(response.developer_trace.steps) == 5
    assert response.developer_trace.steps[-1].name == "Verify Message Delivery"


@pytest.mark.asyncio
async def test_e2e_quantum_workflow():
    container = Container()
    container.model_router.default_provider = "mock"

    req = ChatRequest(
        message="Solve this graph optimization problem using QAOA quantum computing",
        sessionId="session_e2e_03",
    )
    response = await container.orchestrator.process_chat(req)

    assert response.status == "completed"
    assert "quantum" in response.reply.lower() or "verified" in response.reply.lower()


@pytest.mark.asyncio
async def test_e2e_app_launch_flow():
    container = Container()
    container.model_router.default_provider = "mock"

    req = ChatRequest(
        message="Open VS Code",
        sessionId="session_e2e_04",
        developerMode=True,
    )
    response = await container.orchestrator.process_chat(req)

    assert response.status == "completed"
    assert "Vs Code" in response.reply or "VS Code" in response.reply or "open" in response.reply.lower()
    assert response.developer_trace is not None
    assert len(response.developer_trace.steps) == 2


@pytest.mark.asyncio
async def test_e2e_screenshot_flow():
    container = Container()
    container.model_router.default_provider = "mock"

    req = ChatRequest(
        message="Take a screenshot",
        sessionId="session_e2e_05",
        developerMode=True,
    )
    response = await container.orchestrator.process_chat(req)

    assert response.status == "completed"
    assert "screenshot" in response.reply.lower()
    assert response.developer_trace is not None
    assert len(response.developer_trace.steps) == 2


@pytest.mark.asyncio
async def test_e2e_browser_search_flow():
    container = Container()
    container.model_router.default_provider = "mock"

    req = ChatRequest(
        message="Open Chrome and search for Razorpay",
        sessionId="session_e2e_06",
        developerMode=True,
    )
    response = await container.orchestrator.process_chat(req)

    assert response.status == "completed"
    assert response.developer_trace is not None
    assert len(response.developer_trace.steps) == 2

