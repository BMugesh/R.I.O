"""End-to-End Integration Tests for R.I.O. M5.x Voice Runtime & Conversational Agent."""

import pytest
from runtime.state import RuntimeState
from services.conversation.manager import ConversationManager
from services.model_router.router import ModelRouter
from services.voice.manager import VoiceRuntimeManager
from services.voice.tts import MockTTSProvider, TTSManager

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_end_to_end_m5_voice_session():
    """Verify complete end-to-end conversational and action lifecycle:
    STANDBY -> 'Hey RIO' ('Yes?') -> ACTIVE -> 'Open Chrome' ('Chrome is open.') ->
    remains ACTIVE -> Conversational inquiry -> remains ACTIVE ->
    'RIO, standby' ('Standing by.') -> STANDBY -> 'Hey RIO' -> ACTIVE ->
    'RIO, shut down' ('Shutting down.').
    """
    mock_tts = MockTTSProvider()
    tts_mgr = TTSManager(provider=mock_tts)
    mr = ModelRouter(default_provider="mock")
    conv_mgr = ConversationManager(model_router=mr)

    voice_mgr = VoiceRuntimeManager(
        tts_manager=tts_mgr,
        command_handler=lambda text: conv_mgr.handle_user_utterance(text),
    )

    # 1. Start in STANDBY
    await voice_mgr.start()
    assert voice_mgr.is_standby is True

    # 2. User says "Hey RIO"
    reply = await voice_mgr.process_user_speech("Hey RIO")
    assert reply == "Yes?"
    assert voice_mgr.is_active is True
    assert "Yes?" in mock_tts.spoken_history

    # 3. User says "Open Chrome" (WITHOUT repeating wake word!)
    action_reply = await voice_mgr.process_user_speech("Open Chrome")
    assert "chrome is open" in action_reply.lower()

    # 4. Crucial: System REMAINS ACTIVE!
    assert voice_mgr.is_active is True

    # 5. User asks conversational question
    conv_reply = await voice_mgr.process_user_speech("What is the difference between RAG and fine-tuning?")
    assert len(conv_reply) > 0
    assert voice_mgr.is_active is True

    # 6. User says "RIO, standby"
    standby_reply = await voice_mgr.process_user_speech("RIO, standby")
    assert "standing by" in standby_reply.lower()
    assert voice_mgr.is_standby is True

    # 7. User says "Hey RIO" again to wake up
    wake_again = await voice_mgr.process_user_speech("Hey RIO")
    assert wake_again == "Yes?"
    assert voice_mgr.is_active is True

    # 8. User says "RIO, shut down"
    shutdown_reply = await voice_mgr.process_user_speech("RIO, shut down")
    assert "shutting down" in shutdown_reply.lower()

    await voice_mgr.stop()
