"""Unit tests for Groq Conversational Reasoning layer (Milestone 5.x)."""

import pytest
from services.conversation.history import ConversationHistory
from services.model_router.router import ModelRouter

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_groq_conversational_generate():
    """Verify ModelRouter generates natural conversation with Groq / Mock provider."""
    router = ModelRouter(default_provider="mock")
    history = ConversationHistory()
    history.add_user_message("What is RAG?")

    messages = history.get_groq_messages()
    res = await router.generate(
        task_type="conversation",
        messages=messages,
        complexity="medium",
    )

    assert "content" in res
    assert res.get("role") == "assistant"
    assert len(res["content"]) > 0
