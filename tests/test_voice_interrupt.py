"""Unit tests for Voice Interruption Handling (Milestone 5.x)."""

import pytest
from services.voice.manager import VoiceRuntimeManager
from services.voice.tts import MockTTSProvider, TTSManager

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_voice_interruption_stops_playback():
    """Verify 'RIO, stop' halts active speech output immediately."""
    provider = MockTTSProvider()
    tts = TTSManager(provider=provider)
    mgr = VoiceRuntimeManager(tts_manager=tts)
    await mgr.start()

    # Enqueue text and trigger stop
    await tts.speak("Playing a long response...")
    reply = await mgr.process_user_speech("RIO, stop")

    assert reply == "Stopped."
    assert provider._interrupted is True

    await mgr.stop()
