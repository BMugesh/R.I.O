"""Integration tests for ConversationManager (Milestone 5.x)."""

import pytest
from services.conversation.context import ConversationContext
from services.conversation.intent import IntentClassifier, IntentType
from services.conversation.manager import ConversationManager
from services.model_router.router import ModelRouter

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_multi_turn_conversation_flow():
    """Verify natural conversational dialogue across multiple turns."""
    mr = ModelRouter(default_provider="mock")
    mgr = ConversationManager(model_router=mr)

    # Turn 1: Conversational question
    intent1, reply1 = await mgr.handle_user_utterance("What is the difference between PyTorch and TensorFlow?")
    assert intent1 == IntentType.CONVERSATIONAL
    assert len(reply1) > 0
    assert mgr.history.turn_count == 1

    # Turn 2: Follow-up question using context
    intent2, reply2 = await mgr.handle_user_utterance("Which one would you recommend for my StockGenie project?")
    assert intent2 == IntentType.CONVERSATIONAL
    assert len(reply2) > 0
    assert mgr.history.turn_count == 2


@pytest.mark.asyncio
async def test_conversation_manager_standby_and_shutdown():
    """Verify system commands are detected and return appropriate replies."""
    mr = ModelRouter(default_provider="mock")
    mgr = ConversationManager(model_router=mr)

    intent, reply = await mgr.handle_user_utterance("RIO, standby")
    assert intent == IntentType.SYSTEM_STANDBY
    assert "standing by" in reply.lower()

    intent_sd, reply_sd = await mgr.handle_user_utterance("RIO, shut down")
    assert intent_sd == IntentType.SYSTEM_SHUTDOWN
    assert "shutting down" in reply_sd.lower()


@pytest.mark.asyncio
async def test_polite_action_classification_and_execution():
    """Verify natural polite phrasing ('Can you open me WhatsApp?') triggers action execution."""
    mr = ModelRouter(default_provider="mock")
    mgr = ConversationManager(model_router=mr)

    # Test IntentClassifier directly
    intent, contract = IntentClassifier.classify("Can you open me WhatsApp?")
    assert intent == IntentType.ACTION
    assert contract is not None
    assert contract.goal.lower() == "open whatsapp"

    intent2, contract2 = IntentClassifier.classify("Please open Chrome")
    assert intent2 == IntentType.ACTION
    assert contract2 is not None
    assert contract2.goal.lower() == "open chrome"

    intent3, contract3 = IntentClassifier.classify("Can you explain how neural networks work?")
    assert intent3 == IntentType.CONVERSATIONAL
    assert contract3 is None
