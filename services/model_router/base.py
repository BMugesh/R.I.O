"""Base Model Provider Interface for R.I.O."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseModelProvider(ABC):
    """Abstract base class for all AI Model Providers."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier."""
        pass

    @abstractmethod
    async def generate(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a response from the specified model."""
        pass

    @abstractmethod
    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        model: str = "whisper-large-v3-turbo",
        language: Optional[str] = "en",
    ) -> str:
        """Transcribe speech audio bytes to text."""
        pass
