"""Context Engine for R.I.O.

Synthesizes multi-turn conversation history, relevant long-term semantic memories,
and connected device state into a unified reasoning context.
"""

from typing import Any, Dict, List, Optional
from packages.schemas.input import RIOInput
from packages.schemas.memory import MemoryItem
from services.memory.memory_manager import MemoryManager


class ContextEngine:
    """Manages the full context envelope for reasoning and agent execution."""

    def __init__(self, memory_manager: Optional[MemoryManager] = None):
        self.memory_manager = memory_manager or MemoryManager()

    async def build_context(
        self,
        rio_input: RIOInput,
        active_device_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Assemble comprehensive context for reasoning."""
        session_id = rio_input.metadata.session_id or "default_session"
        user_id = rio_input.metadata.user_id or "default_user"
        user_text = rio_input.get_text_content()

        # 1. Fetch recent conversational turns
        recent_turns = await self.memory_manager.get_recent_turns(session_id=session_id, count=6)

        # 2. Semantic recall of relevant long-term memories
        memories: List[MemoryItem] = []
        if user_text:
            memories = await self.memory_manager.recall(
                query_text=user_text,
                user_id=user_id,
                limit=3,
            )

        # 3. Assemble unified context dictionary
        context = {
            "session_id": session_id,
            "user_id": user_id,
            "input_type": rio_input.type.value,
            "recent_turns": recent_turns,
            "relevant_memories": [m.content for m in memories],
            "active_device_id": active_device_id or rio_input.metadata.device_id,
            "timestamp": rio_input.timestamp,
        }
        return context
