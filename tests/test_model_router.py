"""Unit tests for Model Router and capability-based routing."""

import pytest
from services.model_router.router import ModelRouter


@pytest.mark.asyncio
async def test_capability_routing_resolution():
    router = ModelRouter(default_provider="mock")

    assert router.resolve_model("complex_reasoning") == "openai/gpt-oss-120b"
    assert router.resolve_model("agent_task") == "openai/gpt-oss-20b"
    assert router.resolve_model("conversation") == "openai/gpt-oss-120b"
    assert router.resolve_model("fast_classification") == "openai/gpt-oss-20b"
    assert router.resolve_model("web_research") == "openai/gpt-oss-120b"



@pytest.mark.asyncio
async def test_model_generate_mock():
    router = ModelRouter(default_provider="mock")
    res = await router.generate(
        task_type="conversation",
        messages=[{"role": "user", "content": "Hello RIO"}],
    )
    assert "content" in res
    assert res["role"] == "assistant"


@pytest.mark.asyncio
async def test_transcribe_mock():
    router = ModelRouter(default_provider="mock")
    text = await router.transcribe(audio_bytes=b"dummy_bytes")
    assert "transcription" in text.lower()
