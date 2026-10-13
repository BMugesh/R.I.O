"""Groq-Exclusive Capability-Based Model Router for R.I.O.

Directs all intelligence tasks exclusively to specialized Groq production models:
- openai/gpt-oss-120b: Complex reasoning, planning, coding, high-level decisions
- openai/gpt-oss-20b: Fast agent workers, general conversation, tool extraction
- groq/compound & groq/compound-mini: Autonomous research, web and tool execution
- whisper-large-v3-turbo: Real-time speech-to-text
"""

from enum import Enum
import os
import re
from typing import Any, Dict, List, Optional
import time
from services.model_router.adaptive_router import AdaptiveModelRouter
from services.model_router.base import BaseModelProvider
from services.model_router.providers.groq_provider import GroqProvider
from services.model_router.providers.mock_provider import MockProvider


class RouteStrategy(str, Enum):
    """Execution strategy determining whether local compute, AI, or a hybrid is required."""
    NO_AI_REQUIRED = "NO_AI_REQUIRED"
    LOCAL_MODEL = "LOCAL_MODEL"
    GROQ = "GROQ"
    HYBRID = "HYBRID"


class ModelRouter:
    """Central Model Router for R.I.O. (Groq Primary + Adaptive Scoring)."""

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
        elif os.getenv("RIO_ENV") == "test":
            self.default_provider = os.getenv("DEFAULT_MODEL_PROVIDER", "mock")
        else:
            self.default_provider = os.getenv("DEFAULT_MODEL_PROVIDER", "groq")
        self.providers: Dict[str, BaseModelProvider] = {
            "groq": GroqProvider(),
            "mock": MockProvider(),
        }
        self.adaptive_router = AdaptiveModelRouter()

    def get_provider(self, provider_name: Optional[str] = None) -> BaseModelProvider:
        name = provider_name or self.default_provider
        return self.providers.get(name, self.providers["groq"])

    def determine_route_strategy(self, query: str, task_type: Optional[str] = None) -> RouteStrategy:
        """Determine whether query requires local execution, AI reasoning, local model, or hybrid.
        
        Rules:
        - Pure local computer/device queries -> NO_AI_REQUIRED
        - Diagnostic questions combining local facts with interpretation -> HYBRID
        - Local embeddings, hashing, or fast classification -> LOCAL_MODEL
        - Deep semantic reasoning, planning, code generation, summarization -> GROQ
        """
        if not query or not query.strip():
            return RouteStrategy.NO_AI_REQUIRED

        q = query.strip().lower()

        # Hybrid: Diagnostic or performance analysis requiring local data + AI reasoning
        if any(h in q for h in (
            "analyze my laptop performance", "analyze my performance", "diagnose my laptop",
            "diagnose why", "what is slowing down", "analyze my pc", "analyze why",
            "check my computer and tell me what is wrong", "what is wrong with my laptop"
        )):
            return RouteStrategy.HYBRID

        # Pure Local System Queries & Hardware Telemetry
        local_system_patterns = [
            r"\b(?:what(?:'s|\s+is)?(?:\s+the)?\s+time|current\s+time|tell\s+me\s+the\s+time|time\s+now)\b",
            r"\b(?:what(?:'s|\s+is)?(?:\s+the|\s+today's)?\s+date|what\s+day\s+is\s+(?:it|today)|today's\s+date)\b",
            r"\b(?:what(?:'s|\s+is)?(?:\s+the)?\s+timezone|what\s+timezone)\b",
            r"\b(?:what\s+gpu(?:\s+do\s+i\s+have)?|what(?:'s|\s+is)?(?:\s+my)?\s+gpu|show(?:\s+my)?\s+gpu|gpu\s+usage|gpu\s+temp(?:erature)?|how\s+much\s+vram)\b",
            r"\b(?:how\s+much\s+ram|what(?:'s|\s+is)?(?:\s+my)?\s+ram|ram\s+usage|memory\s+usage|how\s+much\s+memory|ram\s+is\s+free|free\s+ram|free\s+memory)\b",
            r"\b(?:what(?:'s|\s+is)?(?:\s+my)?\s+cpu|cpu\s+usage|cpu\s+load|how\s+many\s+cores)\b",
            r"\b(?:what(?:'s|\s+is)?(?:\s+my)?\s+battery|battery\s+(?:level|status|percentage)|is(?:\s+(?:the|my))?\s+laptop\s+plugged\s+in|laptop\s+plugged\s+in|is\s+plugged\s+in)\b",
            r"\b(?:how\s+much\s+disk|disk\s+space|free\s+space|storage\s+space)\b",
            r"\b(?:what\s+windows\s+are\s+open|list\s+open\s+windows|what\s+apps\s+are\s+open|running\s+processes|list\s+processes)\b",
            r"\b(?:what\s+os|what\s+operating\s+system|what\s+windows\s+version)\b",
            r"\b(?:is\s+[a-zA-Z0-9\-_ ]+\s+(?:running|open|active)|check\s+if\s+[a-zA-Z0-9\-_ ]+\s+is\s+(?:running|open|active))\b",
        ]
        if any(re.search(pat, q) for pat in local_system_patterns):
            return RouteStrategy.NO_AI_REQUIRED

        # Pure Local OS / App Controls (without questions or reasoning)
        if any(q.startswith(v + " ") for v in (
            "open", "launch", "start", "close", "terminate", "kill",
            "minimize", "maximize", "focus", "switch to", "screenshot", "take a screenshot"
        )) and not any(k in q for k in ("why", "explain", "how do", "analyze", "write", "generate", "code")):
            return RouteStrategy.NO_AI_REQUIRED

        if task_type in ("system_telemetry", "system.time.read", "system.hardware_telemetry", "system_gpu_telemetry"):
            return RouteStrategy.NO_AI_REQUIRED

        if task_type in ("embeddings", "reranker", "fast_classification"):
            return RouteStrategy.LOCAL_MODEL

        return RouteStrategy.GROQ


    def resolve_model(
        self,
        task_type: str,
        explicit_model: Optional[str] = None,
        complexity: Optional[str] = None,
        latency_sensitive: bool = False,
        requires_tools: bool = False,
        privacy: str = "remote_allowed",
    ) -> str:
        """Resolve model name from capability/task_type or via adaptive multi-criteria scoring."""
        if explicit_model:
            return explicit_model

        if complexity is not None or latency_sensitive or requires_tools:
            return self.adaptive_router.select_best_model(
                task_type=task_type,
                complexity=complexity or "medium",
                latency_sensitive=latency_sensitive,
                requires_tools=requires_tools,
                privacy=privacy,
            )

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
        complexity: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate response via Groq with adaptive selection and telemetry tracking."""
        target_model = self.resolve_model(task_type, explicit_model=model, complexity=complexity)
        prov = self.get_provider(provider)
        msgs = messages or []
        start_t = time.time()
        success = False
        try:
            res = await prov.generate(
                model=target_model,
                messages=msgs,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                response_format=response_format,
            )
            success = True
            return res
        except Exception as e:
            if provider == "mock":
                mock_prov = self.providers["mock"]
                res = await mock_prov.generate(
                    model=target_model,
                    messages=msgs,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                success = True
                return res
            raise e
        finally:
            elapsed_ms = (time.time() - start_t) * 1000
            self.adaptive_router.record_outcome(task_type=task_type, model_name=target_model, latency_ms=elapsed_ms, success=success)

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
