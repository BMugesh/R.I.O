"""Conversation History Store for R.I.O. (Milestone 5.x).

Stores recent dialogue turns and produces trimmed history for Groq reasoning.
"""

from typing import Any, Dict, List, Optional
from services.conversation.message import ConversationMessage, MessageRole


class ConversationHistory:
    """Manages sequential dialogue history with sliding window trimming."""

    def __init__(self, max_messages: int = 20):
        self.max_messages = max_messages
        self._messages: List[ConversationMessage] = []

    def add_user_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self._messages.append(ConversationMessage(role=MessageRole.USER, content=content, metadata=metadata or {}))
        self._trim()

    def add_assistant_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self._messages.append(ConversationMessage(role=MessageRole.ASSISTANT, content=content, metadata=metadata or {}))
        self._trim()

    def add_system_message(self, content: str) -> None:
        self._messages.append(ConversationMessage(role=MessageRole.SYSTEM, content=content))
        self._trim()

    def _trim(self) -> None:
        if len(self._messages) > self.max_messages:
            self._messages = self._messages[-self.max_messages:]

    def get_messages(self) -> List[ConversationMessage]:
        return list(self._messages)

    def get_groq_messages(self) -> List[Dict[str, str]]:
        """Return history formatted as standard OpenAI/Groq message dictionaries."""
        return [{"role": m.role.value, "content": m.content} for m in self._messages]

    def clear(self) -> None:
        self._messages.clear()

    @property
    def turn_count(self) -> int:
        return sum(1 for m in self._messages if m.role == MessageRole.USER)
