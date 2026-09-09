"""Unit tests for Memory subsystem (short-term & semantic)."""

import pytest
from services.memory.memory_manager import MemoryManager


@pytest.mark.asyncio
async def test_short_term_conversation_memory():
    manager = MemoryManager()
    session_id = "test_session_1"

    await manager.add_conversation_turn(session_id, "user", "Hi RIO")
    await manager.add_conversation_turn(session_id, "assistant", "Hello! How can I help?")

    turns = await manager.get_recent_turns(session_id, count=5)
    assert len(turns) == 2
    assert turns[0]["role"] == "user"
    assert turns[1]["content"] == "Hello! How can I help?"


@pytest.mark.asyncio
async def test_semantic_memory_store_recall_forget():
    manager = MemoryManager()

    # Store
    item = await manager.store_semantic(
        content="User loves black coffee with no sugar",
        user_id="user_123",
        importance=0.9,
        tags=["coffee", "preference"],
    )
    assert item.id is not None

    # Recall
    results = await manager.recall("coffee preferences", user_id="user_123")
    assert len(results) >= 1
    assert "coffee" in results[0].content.lower()

    # User-controlled Forget
    forgotten_count = await manager.forget_topic("coffee", user_id="user_123")
    assert forgotten_count == 1

    # Recall after forget
    after_results = await manager.recall("coffee preferences", user_id="user_123")
    assert len(after_results) == 0
