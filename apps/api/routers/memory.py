"""Memory API Router."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from packages.schemas.memory import MemoryItem, MemoryQuery, MemoryType
from apps.api.deps import Container, get_container

router = APIRouter(prefix="/memory", tags=["Memory"])


@router.get("", response_model=List[MemoryItem])
async def search_memories(
    query: str,
    user_id: Optional[str] = "default_user",
    limit: int = 10,
    container: Container = Depends(get_container),
):
    """Semantic search over long-term memories."""
    return await container.memory_manager.recall(query_text=query, user_id=user_id, limit=limit)


@router.post("", response_model=MemoryItem)
async def store_memory(item: MemoryItem, container: Container = Depends(get_container)):
    """Explicitly store a fact or preference in long-term memory."""
    return await container.memory_manager.store_semantic(
        content=item.content,
        user_id=item.user_id or "default_user",
        memory_type=item.type,
        importance=item.importance,
        tags=item.tags,
        metadata=item.metadata,
    )


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str, container: Container = Depends(get_container)):
    """Delete a memory item by ID."""
    success = await container.memory_manager.forget(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "deleted", "id": memory_id}


@router.post("/forget")
async def forget_topic(topic: str, user_id: Optional[str] = "default_user", container: Container = Depends(get_container)):
    """User privacy control: Forget all memories matching a topic."""
    count = await container.memory_manager.forget_topic(topic=topic, user_id=user_id)
    return {"status": "success", "forgotten_count": count, "topic": topic}
