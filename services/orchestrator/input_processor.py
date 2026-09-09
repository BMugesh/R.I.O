"""Universal Input Processor for R.I.O.

Normalizes incoming raw user inputs, audio chunks, images, documents, and device signals
into standard RIOInput envelopes.
"""

from typing import Any, Dict, Optional
from packages.schemas.input import InputMetadata, InputType, RIOInput


class InputProcessor:
    """Processes and normalizes incoming data."""

    @staticmethod
    def process_raw(
        raw_payload: Any,
        input_type: InputType = InputType.TEXT,
        source: str = "web_chat",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RIOInput:
        """Create a normalized RIOInput envelope."""
        meta_obj = InputMetadata(**(metadata or {}))
        return RIOInput(
            type=input_type,
            source=source,
            payload=raw_payload,
            metadata=meta_obj,
        )

    @staticmethod
    def from_chat_message(text: str, session_id: Optional[str] = None, user_id: str = "default_user") -> RIOInput:
        """Quick constructor for simple chat text."""
        return RIOInput(
            type=InputType.TEXT,
            source="web_chat",
            payload=text,
            metadata=InputMetadata(session_id=session_id, user_id=user_id),
        )
