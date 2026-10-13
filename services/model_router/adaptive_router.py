"""Adaptive Model Router for R.I.O. (Milestone 5).

Multi-criteria scoring, policy filtering, and bounded telemetry for
intelligent model selection across Groq production models.
"""

from collections import deque
from dataclasses import dataclass, field
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("rio.model_router.adaptive")


@dataclass
class ModelProfile:
    """Capability and operational profile for a supported model."""
    name: str
    reasoning_strength: float  # 0.0 - 1.0
    latency_tier: float        # 0.0 (slow) - 1.0 (ultra-fast)
    tool_strength: float       # 0.0 - 1.0
    cost_factor: float         # 0.0 (cheap) - 1.0 (expensive)
    max_context_tokens: int
    is_local: bool = False


# Supported production Groq model profiles
PROFILES: Dict[str, ModelProfile] = {
    "llama-3.1-8b-instant": ModelProfile(
        name="llama-3.1-8b-instant",
        reasoning_strength=0.5,
        latency_tier=0.95,
        tool_strength=0.6,
        cost_factor=0.1,
        max_context_tokens=8192,
    ),
    "openai/gpt-oss-20b": ModelProfile(
        name="openai/gpt-oss-20b",
        reasoning_strength=0.75,
        latency_tier=0.85,
        tool_strength=0.85,
        cost_factor=0.3,
        max_context_tokens=16384,
    ),
    "openai/gpt-oss-120b": ModelProfile(
        name="openai/gpt-oss-120b",
        reasoning_strength=0.98,
        latency_tier=0.60,
        tool_strength=0.95,
        cost_factor=0.8,
        max_context_tokens=32768,
    ),
    "groq/compound": ModelProfile(
        name="groq/compound",
        reasoning_strength=0.90,
        latency_tier=0.50,
        tool_strength=0.98,
        cost_factor=0.7,
        max_context_tokens=32768,
    ),
    "whisper-large-v3-turbo": ModelProfile(
        name="whisper-large-v3-turbo",
        reasoning_strength=0.4,
        latency_tier=0.90,
        tool_strength=0.1,
        cost_factor=0.2,
        max_context_tokens=4096,
    ),
}


@dataclass
class RoutingTelemetryRecord:
    """Historical telemetry record for bounded routing memory."""
    task_type: str
    model_name: str
    latency_ms: float
    success: bool
    timestamp: float = field(default_factory=time.time)


class AdaptiveModelRouter:
    """Calculates model suitability scores based on multi-factor heuristics and historical reliability."""

    def __init__(self, history_size: int = 100):
        self.profiles = dict(PROFILES)
        self._history: deque[RoutingTelemetryRecord] = deque(maxlen=history_size)

    def record_outcome(self, task_type: str, model_name: str, latency_ms: float, success: bool) -> None:
        """Record bounded telemetry for a model execution."""
        self._history.append(
            RoutingTelemetryRecord(
                task_type=task_type,
                model_name=model_name,
                latency_ms=latency_ms,
                success=success,
            )
        )

    def get_model_reliability(self, model_name: str) -> float:
        """Calculate historical reliability (0.0 to 1.0) with Bayesian smoothing."""
        records = [r for r in self._history if r.model_name == model_name]
        if not records:
            return 1.0  # Default to high confidence for untested models
        successes = sum(1 for r in records if r.success)
        return (successes + 2.0) / (len(records) + 2.0)

    def score_model(
        self,
        profile: ModelProfile,
        task_type: str,
        complexity: str = "medium",
        latency_sensitive: bool = False,
        requires_tools: bool = False,
        privacy: str = "remote_allowed",
    ) -> float:
        """Compute heuristic suitability score for a candidate model.

        Score = task_fit + reasoning_fit + latency_fit + tool_fit + reliability - cost - privacy_penalty
        """
        # 1. Reasoning Fit based on complexity
        if complexity == "extreme":
            reasoning_fit = profile.reasoning_strength * 6.0
        elif complexity == "high" or task_type in ("complex_reasoning", "planning", "coding"):
            reasoning_fit = profile.reasoning_strength * 4.0
        elif complexity == "low" or task_type in ("fast_classification", "intent_detection"):
            reasoning_fit = (1.0 - profile.reasoning_strength) * 2.0  # Prefer lighter models
        else:
            reasoning_fit = profile.reasoning_strength * 2.0

        # 2. Latency Fit
        latency_fit = profile.latency_tier * (3.0 if latency_sensitive else 1.0)

        # 3. Tool Fit
        tool_fit = profile.tool_strength * (3.0 if requires_tools else 0.5)

        # 4. Reliability
        reliability = self.get_model_reliability(profile.name) * 2.0

        # 5. Cost penalty
        cost_penalty = profile.cost_factor * 1.0

        # 6. Privacy Penalty
        privacy_penalty = 0.0
        if privacy == "local_only" and not profile.is_local:
            privacy_penalty = 100.0  # Disqualify remote models in strict local mode

        return reasoning_fit + latency_fit + tool_fit + reliability - cost_penalty - privacy_penalty

    def select_best_model(
        self,
        task_type: str,
        complexity: str = "medium",
        latency_sensitive: bool = False,
        requires_tools: bool = False,
        privacy: str = "remote_allowed",
        explicit_candidates: Optional[List[str]] = None,
    ) -> str:
        """Select the highest scoring model given operational constraints."""
        candidates = explicit_candidates or list(self.profiles.keys())
        # Filter out STT for text tasks
        if task_type != "speech_to_text":
            candidates = [c for c in candidates if c != "whisper-large-v3-turbo"]
        else:
            return "whisper-large-v3-turbo"

        scored: List[tuple[str, float]] = []
        for model_name in candidates:
            profile = self.profiles.get(model_name)
            if not profile:
                continue
            score = self.score_model(
                profile=profile,
                task_type=task_type,
                complexity=complexity,
                latency_sensitive=latency_sensitive,
                requires_tools=requires_tools,
                privacy=privacy,
            )
            scored.append((model_name, score))

        if not scored:
            return "openai/gpt-oss-20b"

        scored.sort(key=lambda x: x[1], reverse=True)
        best_model, best_score = scored[0]
        logger.debug(f"AdaptiveModelRouter selected {best_model} (score={best_score:.2f}) for task={task_type}, complexity={complexity}")
        return best_model
