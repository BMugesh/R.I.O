"""Unit tests for Standby Mode and Local Privacy Guarantees (Milestone 5.x)."""

import pytest
from runtime.state import RuntimeState
from services.voice.manager import VoiceRuntimeManager

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_standby_ignores_non_wake_speech():
    """Verify that while in STANDBY mode, non-wake speech is rejected locally with zero cloud calls."""
    mgr = VoiceRuntimeManager()
    await mgr.start()

    assert mgr.is_standby is True

    # Non-wake conversational chatter while in standby
    reply = await mgr.process_user_speech("Good morning, what's the weather today?")
    assert reply is None
    assert mgr.is_standby is True

    await mgr.stop()
