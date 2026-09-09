"""Unified Memory Manager for R.I.O.

Coordinates short-term working memory, episodic task logs, semantic long-term memory,
and user-controlled privacy/forgetting policies.
"""

from typing import Any, Dict, List, Optional
from packages.schemas.memory import MemoryItem, MemoryPolicy, MemoryQuery, MemoryType
from services.memory.cache_store import CacheStore
from services.memory.vector_store import VectorStore


class MemoryManager:
    """Central Memory Management subsystem."""

    def __init__(self, vector_store: Optional[VectorStore] = None, cache_store: Optional[CacheStore] = None):
        self.vector_store = vector_store or VectorStore()
        self.cache_store = cache_store or CacheStore()
        self.policy = MemoryPolicy()

    async def add_conversation_turn(self, session_id: str, role: str, content: str) -> None:
        """Record a turn in short-term conversation memory."""
        cache_key = f"session:{session_id}:turns"
        turns = await self.cache_store.get(cache_key) or []
        turns.append({"role": role, "content": content})
        if len(turns) > self.policy.max_short_term_turns:
            turns = turns[-self.policy.max_short_term_turns :]
        await self.cache_store.set(cache_key, turns, ttl_seconds=86400)

    async def get_recent_turns(self, session_id: str, count: int = 10) -> List[Dict[str, str]]:
        """Retrieve recent conversational turns for context window."""
        cache_key = f"session:{session_id}:turns"
        turns = await self.cache_store.get(cache_key) or []
        return turns[-count:]

    async def store_semantic(
        self,
        content: str,
        user_id: Optional[str] = "default_user",
        memory_type: MemoryType = MemoryType.SEMANTIC,
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryItem:
        """Store long-term semantic memory."""
        item = MemoryItem(
            user_id=user_id,
            type=memory_type,
            content=content,
            importance=importance,
            tags=tags or [],
            metadata=metadata or {},
        )
        await self.vector_store.store(item)
        return item

    async def recall(
        self,
        query_text: str,
        user_id: Optional[str] = "default_user",
        limit: int = 5,
        types: Optional[List[MemoryType]] = None,
    ) -> List[MemoryItem]:
        """Recall relevant long-term memories for given input."""
        q = MemoryQuery(
            text=query_text,
            user_id=user_id,
            limit=limit,
            types=types,
        )
        return await self.vector_store.search(q)

    async def forget(self, memory_id: str) -> bool:
        """Delete specific memory record."""
        return await self.vector_store.delete(memory_id)

    async def forget_topic(self, topic: str, user_id: str = "default_user") -> int:
        """User-controlled forgetting: removes all records matching topic."""
        return await self.vector_store.forget_by_topic(user_id=user_id, topic=topic)
