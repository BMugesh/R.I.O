"""Mock Model Provider for offline development and CI/CD testing."""

from typing import Any, Dict, List, Optional
from services.model_router.base import BaseModelProvider


class MockProvider(BaseModelProvider):
    """Deterministic Mock Provider for unit testing."""

    @property
    def provider_name(self) -> str:
        return "mock"

    async def generate(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        last_msg = messages[-1]["content"] if messages else ""
        return {
            "content": f"Mock response for [{model}]: Processed successfully.",
            "role": "assistant",
            "model": model,
            "tool_calls": [],
        }

    async def transcribe_audio(self, audio_bytes: bytes, model: str = "", language: Optional[str] = "en") -> str:
        return "Mock audio transcription completed."
