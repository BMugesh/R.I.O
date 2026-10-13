"""Unit tests for R.I.O. M5.3 Adaptive Model Routing."""

import pytest
pytestmark = [pytest.mark.unit]

from services.model_router.adaptive_router import AdaptiveModelRouter
from services.model_router.router import ModelRouter


def test_adaptive_router_heuristic_selection():
    router = AdaptiveModelRouter()

    # Fast / low complexity task prefers low latency
    fast_model = router.select_best_model(
        task_type="fast_classification",
        complexity="low",
        latency_sensitive=True,
    )
    assert fast_model == "llama-3.1-8b-instant"

    # Extreme complexity prefers deep reasoning
    heavy_model = router.select_best_model(
        task_type="complex_reasoning",
        complexity="extreme",
    )
    assert heavy_model == "openai/gpt-oss-120b"

    # Tool-heavy task prefers tool-capable compound models
    tool_model = router.select_best_model(
        task_type="tool_heavy_research",
        requires_tools=True,
    )
    assert tool_model in ("groq/compound", "openai/gpt-oss-120b")

    # Speech to text always routes to whisper
    stt_model = router.select_best_model(task_type="speech_to_text")
    assert stt_model == "whisper-large-v3-turbo"


def test_adaptive_router_telemetry_and_reliability():
    router = AdaptiveModelRouter(history_size=10)

    # Initially 1.0 reliability
    assert router.get_model_reliability("openai/gpt-oss-20b") == 1.0

    # Record 3 failures and 1 success
    router.record_outcome("conversation", "openai/gpt-oss-20b", 120.0, False)
    router.record_outcome("conversation", "openai/gpt-oss-20b", 130.0, False)
    router.record_outcome("conversation", "openai/gpt-oss-20b", 110.0, False)
    router.record_outcome("conversation", "openai/gpt-oss-20b", 100.0, True)

    rel = router.get_model_reliability("openai/gpt-oss-20b")
    # (1 success + 2 smoothing) / (4 total + 2 smoothing) = 3 / 6 = 0.5
    assert 0.4 < rel < 0.6


@pytest.mark.asyncio
async def test_model_router_adaptive_integration():
    router = ModelRouter(default_provider="mock")

    # Direct resolution preserves backward compatibility
    m1 = router.resolve_model("complex_reasoning")
    assert m1 == "openai/gpt-oss-120b"

    # Adaptive resolution via parameters
    m2 = router.resolve_model("classification", complexity="low", latency_sensitive=True)
    assert m2 == "llama-3.1-8b-instant"

    # Generate records telemetry
    res = await router.generate(
        task_type="fast_classification",
        messages=[{"role": "user", "content": "ping"}],
        complexity="low",
    )
    assert res is not None
    assert len(router.adaptive_router._history) >= 1
