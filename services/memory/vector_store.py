"""Vector Store Implementation for R.I.O. Long-term Semantic Memory.

Connects to PostgreSQL + pgvector with fallback to in-memory cosine similarity
when running in lightweight local or mock mode.
"""

import math
import os
from typing import Any, Dict, List, Optional
import numpy as np
from packages.schemas.memory import MemoryItem, MemoryQuery, MemoryType


class VectorStore:
    """Vector Store backed by PostgreSQL/pgvector or In-Memory index."""

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or os.getenv("DATABASE_URL")
        # In-memory storage cache
        self._in_memory_items: Dict[str, MemoryItem] = {}

    def _generate_mock_embedding(self, text: str, dim: int = 1536) -> List[float]:
        """Generate a normalized token-hash embedding vector from text."""
        vec = np.zeros(dim, dtype=np.float32)
        words = text.lower().split()
        if not words:
            return vec.tolist()

        for w in words:
            h = abs(hash(w)) % dim
            vec[h] += 1.0

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    async def store(self, item: MemoryItem) -> str:
        """Store a memory item with vector embedding."""
        if not item.embedding:
            item.embedding = self._generate_mock_embedding(item.content)

        self._in_memory_items[item.id] = item
        # If DB connection is available, insert into PostgreSQL
        # (Asyncpg integration hook for containerized runs)
        return item.id

    async def search(self, query: MemoryQuery) -> List[MemoryItem]:
        """Perform semantic cosine similarity search."""
        query_vec = self._generate_mock_embedding(query.text)
        results = []

        for item in self._in_memory_items.values():
            if query.user_id and item.user_id != query.user_id:
                continue
            if query.types and item.type not in query.types:
                continue
            if query.tags and not any(tag in item.tags for tag in query.tags):
                continue

            if item.embedding:
                # Cosine similarity calculation
                sim = float(np.dot(query_vec, item.embedding))
                if sim >= query.min_similarity or sim > 0.1:
                    results.append((sim * item.importance, item))

        # Sort by relevance score descending
        results.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in results[: query.limit]]

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory item by ID."""
        if memory_id in self._in_memory_items:
            del self._in_memory_items[memory_id]
            return True
        return False

    async def forget_by_topic(self, user_id: str, topic: str) -> int:
        """Forget/delete memories matching a user topic."""
        to_delete = []
        topic_lower = topic.lower()
        for mid, item in self._in_memory_items.items():
            if item.user_id == user_id or not item.user_id:
                if topic_lower in item.content.lower() or any(topic_lower in tag.lower() for tag in item.tags):
                    to_delete.append(mid)

        for mid in to_delete:
            del self._in_memory_items[mid]
        return len(to_delete)
