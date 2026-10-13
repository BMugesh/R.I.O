"""Tests for Persistent Semantic Memory (Phase 9).

Validates:
1. Long-term memories are persisted to JSON disk storage.
2. VectorStore reload recreates in-memory index from disk accurately.
3. Cosine similarity search works seamlessly across reloads.
4. Deletion and topic-based forgetting persist immediately to disk.
"""

import os
import shutil
import tempfile
import pytest
from packages.schemas.memory import MemoryItem, MemoryQuery, MemoryType
from services.memory.vector_store import VectorStore
from services.memory.memory_manager import MemoryManager


@pytest.mark.asyncio
async def test_vector_store_disk_persistence():
    """Verify that stored items are physically written to disk and restored in new instance."""
    temp_dir = tempfile.mkdtemp(prefix="rio_mem_test_")
    storage_path = os.path.join(temp_dir, "test_memories.json")

    try:
        vs1 = VectorStore(storage_path=storage_path)
        item1 = MemoryItem(
            user_id="user_1",
            content="User prefers Python over C++ for prototyping",
            importance=0.8,
            tags=["programming", "preference"],
        )
        item2 = MemoryItem(
            user_id="user_1",
            content="Project RIO is an autonomous computer control runtime",
            importance=0.9,
            tags=["project", "rio"],
        )

        await vs1.store(item1)
        await vs1.store(item2)

        # File must physically exist on disk
        assert os.path.exists(storage_path)
        assert os.path.getsize(storage_path) > 0

        # Create fresh VectorStore instance pointing to the same storage path (Simulate Core restart)
        vs2 = VectorStore(storage_path=storage_path)
        assert len(vs2._in_memory_items) == 2
        assert item1.id in vs2._in_memory_items
        assert item2.id in vs2._in_memory_items

        # Search against restored instance
        results = await vs2.search(MemoryQuery(text="Python coding language", user_id="user_1"))
        assert len(results) >= 1
        assert "python" in results[0].content.lower()

        # Test deletion persists
        await vs2.delete(item1.id)

        vs3 = VectorStore(storage_path=storage_path)
        assert len(vs3._in_memory_items) == 1
        assert item1.id not in vs3._in_memory_items
        assert item2.id in vs3._in_memory_items
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_memory_manager_with_persistence():
    """Verify MemoryManager integrates with persistent VectorStore."""
    temp_dir = tempfile.mkdtemp(prefix="rio_mem_mgr_test_")
    storage_path = os.path.join(temp_dir, "test_memories.json")

    try:
        vs = VectorStore(storage_path=storage_path)
        mm1 = MemoryManager(vector_store=vs)

        await mm1.store_semantic(
            content="User runs Windows 11 on an RTX 4050 Laptop GPU",
            user_id="dev_user",
            importance=0.95,
            tags=["hardware", "gpu"],
        )

        # Restore in new MemoryManager
        vs2 = VectorStore(storage_path=storage_path)
        mm2 = MemoryManager(vector_store=vs2)

        recalled = await mm2.recall("Which graphics card does user have?", user_id="dev_user")
        assert len(recalled) >= 1
        assert "rtx 4050" in recalled[0].content.lower()

        # Forget topic and check persistence
        forgotten = await mm2.forget_topic("hardware", user_id="dev_user")
        assert forgotten >= 1

        vs3 = VectorStore(storage_path=storage_path)
        assert len(vs3._in_memory_items) == 0
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
