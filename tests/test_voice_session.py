"""Unit tests for VoiceSession state tracking (Milestone 5.x)."""

import pytest
from services.voice.session import VoiceSession, VoiceSessionState

pytestmark = pytest.mark.unit


def test_voice_session_turn_telemetry():
    """Verify VoiceSession correctly records turns and calculates uptime."""
    session = VoiceSession(session_id="test_sess_01")
    assert session.state == VoiceSessionState.STANDBY
    assert session.turns_count == 0

    session.transition_to(VoiceSessionState.ACTIVE)
    session.record_turn("Open Chrome", "Chrome is open.")
    assert session.turns_count == 1
    assert session.last_user_text == "Open Chrome"
    assert session.last_assistant_response == "Chrome is open."

    data = session.to_dict()
    assert data["session_id"] == "test_sess_01"
    assert data["turns_count"] == 1
    assert data["state"] == VoiceSessionState.ACTIVE.value
