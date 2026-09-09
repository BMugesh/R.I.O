"""Groq-Exclusive Capability-Based Model Router for R.I.O.

Directs all intelligence tasks exclusively to specialized Groq production models:
- openai/gpt-oss-120b: Complex reasoning, planning, coding, high-level decisions
- openai/gpt-oss-20b: Fast agent workers, general conversation, tool extraction
- groq/compound & groq/compound-mini: Autonomous research, web and tool execution
- whisper-large-v3-turbo: Real-time speech-to-text
"""

import os
from typing import Any, Dict, List, Optional
from services.model_router.base import BaseModelProvider
from services.model_router.providers.groq_provider import GroqProvider
from services.model_router.providers.mock_provider import MockProvider


class ModelRouter:
    """Central Model Router for R.I.O. (Groq Primary)."""

    # Capability to Groq Production Model Matrix
    GROQ_MODEL_ROUTING: Dict[str, str] = {
        "complex_reasoning": "openai/gpt-oss-120b",
        "planning": "openai/gpt-oss-120b",
        "coding": "openai/gpt-oss-120b",
        "agent_task": "openai/gpt-oss-20b",
        "tool_selection": "openai/gpt-oss-20b",
        "structured_output": "openai/gpt-oss-20b",
        "conversation": "openai/gpt-oss-120b",
        "summarization": "openai/gpt-oss-120b",
        "fast_classification": "openai/gpt-oss-20b",
        "intent_detection": "openai/gpt-oss-20b",
        "web_research": "openai/gpt-oss-120b",
        "tool_heavy_research": "openai/gpt-oss-120b",
        "speech_to_text": "whisper-large-v3-turbo",
    }



    def __init__(self, default_provider: Optional[str] = None):
        if default_provider is not None:
            self.default_provider = default_provider
        else:
            self.default_provider = os.getenv("DEFAULT_MODEL_PROVIDER", "groq")
        self.providers: Dict[str, BaseModelProvider] = {
            "groq": GroqProvider(),
            "mock": MockProvider(),
        }

    def get_provider(self, provider_name: Optional[str] = None) -> BaseModelProvider:
        name = provider_name or self.default_provider
        return self.providers.get(name, self.providers["groq"])

    def resolve_model(self, task_type: str, explicit_model: Optional[str] = None) -> str:
        """Resolve model name from capability/task_type."""
        if explicit_model:
            return explicit_model
        return self.GROQ_MODEL_ROUTING.get(task_type, "openai/gpt-oss-20b")

    async def generate(
        self,
        task_type: str = "conversation",
        messages: Optional[List[Dict[str, str]]] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate response via Groq."""
        target_model = self.resolve_model(task_type, explicit_model=model)
        prov = self.get_provider(provider)
        msgs = messages or []
        try:
            return await prov.generate(
                model=target_model,
                messages=msgs,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                response_format=response_format,
            )
        except Exception as e:
            # Fallback to mock provider only if requested or in pure offline mode
            if provider == "mock":
                mock_prov = self.providers["mock"]
                return await mock_prov.generate(
                    model=target_model,
                    messages=msgs,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            raise e

    async def transcribe(
        self,
        audio_bytes: bytes,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        language: Optional[str] = "en",
    ) -> str:
        """Transcribe speech audio via Groq Whisper."""
        target_model = model or self.GROQ_MODEL_ROUTING.get("speech_to_text", "whisper-large-v3-turbo")
        prov = self.get_provider(provider)
        try:
            return await prov.transcribe_audio(audio_bytes=audio_bytes, model=target_model, language=language)
        except Exception:
            return await self.providers["mock"].transcribe_audio(audio_bytes=audio_bytes, model=target_model)
