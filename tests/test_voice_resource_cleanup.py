"""Unit tests for Voice Resource Teardown and Cleanup (Milestone 5.x)."""

import asyncio
import pytest
from services.voice.manager import VoiceRuntimeManager
from services.voice.tts import MockTTSProvider, TTSManager

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_voice_runtime_resource_cleanup():
    """Verify VoiceRuntimeManager cleanly releases tasks and queues on stop()."""
    tts = TTSManager(provider=MockTTSProvider())
    mgr = VoiceRuntimeManager(tts_manager=tts)

    await mgr.start()
    assert mgr.is_running is True

    # Simulate speaking
    await tts.speak("Test voice cleanup")

    # Stop manager
    await mgr.stop()
    assert mgr.is_running is False
    assert tts.queue._worker_task is None or tts.queue._worker_task.done()
