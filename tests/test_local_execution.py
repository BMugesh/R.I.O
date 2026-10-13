"""Unit tests for Local-First Execution without WebSocket dependencies (Milestone 5.x)."""

import pytest
from services.conversation.intent import ActionRequestContract
from services.conversation.manager import ConversationManager
from services.model_router.router import ModelRouter

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_action_executes_locally_without_websocket():
    """Verify that action commands route to local orchestrator and agents directly."""
    mr = ModelRouter(default_provider="mock")
    mgr = ConversationManager(model_router=mr)

    contract = ActionRequestContract(
        goal="Open Chrome",
        requires_execution=True,
        target="local_laptop",
    )

    intent, reply = await mgr._execute_action_request(contract)
    assert intent.value == "action"
    assert "chrome is open" in reply.lower()
