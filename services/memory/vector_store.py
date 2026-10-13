import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
from packages.schemas.memory import MemoryItem, MemoryQuery, MemoryType

logger = logging.getLogger("rio.memory.vector_store")


class VectorStore:
    """Vector Store backed by PostgreSQL/pgvector or In-Memory index with JSON disk persistence."""

    def __init__(self, db_url: Optional[str] = None, storage_path: Optional[str] = None):
        self.db_url = db_url or os.getenv("DATABASE_URL")
        default_path = os.getenv("RIO_MEMORY_PATH", os.path.join(os.getcwd(), "data", "memories.json"))
        self.storage_path = Path(storage_path or default_path) if (storage_path or default_path) else None
        # In-memory storage cache
        self._in_memory_items: Dict[str, MemoryItem] = {}
        self._load()

    def _load(self) -> None:
        """Load persisted memory items from disk."""
        if not self.storage_path or not self.storage_path.exists():
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item_data in data:
                        item = MemoryItem(**item_data)
                        self._in_memory_items[item.id] = item
            logger.info(f"Loaded {len(self._in_memory_items)} memories from {self.storage_path}")
        except Exception as e:
            logger.warning(f"Failed to load memories from {self.storage_path}: {e}")

    def _save(self) -> None:
        """Persist memory items to disk."""
        if not self.storage_path:
            return
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump([item.model_dump() for item in self._in_memory_items.values()], f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save memories to {self.storage_path}: {e}")

    def clear(self) -> None:
        """Clear memory cache and remove storage file."""
        self._in_memory_items.clear()
        if self.storage_path and self.storage_path.exists():
            try:
                self.storage_path.unlink()
            except Exception:
                pass

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
        self._save()
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
            self._save()
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
        if to_delete:
            self._save()
        return len(to_delete)
