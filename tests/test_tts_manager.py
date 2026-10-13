"""Unit tests for Female TTS Manager and Speech Queue (Milestone 5.x)."""

import asyncio
import pytest
from services.voice.tts import MockTTSProvider, TTSManager

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_female_tts_manager_configuration():
    """Verify default female voice, language, and speed."""
    provider = MockTTSProvider()
    tts = TTSManager(provider=provider, voice="female", language="en-IN", speed=1.0)

    assert tts.voice == "female"
    assert tts.language == "en-IN"
    assert tts.speed == 1.0

    res = await tts.speak("Hello, RIO is online.", priority=True)
    assert res.success is True
    assert "Hello, RIO is online." in provider.spoken_history


def test_clean_text_for_speech():
    """Verify technical artifacts (JSON, code, markdown) are stripped from speech output."""
    provider = MockTTSProvider()
    tts = TTSManager(provider=provider)

    raw = 'Done. ```bash\npytest\n``` Status is `success` with {"step_id": 1, "status": "completed"} verified.'
    cleaned = tts.clean_text_for_speech(raw)

    assert "```" not in cleaned
    assert "{" not in cleaned
    assert "}" not in cleaned
    assert "`" not in cleaned
    assert "Done." in cleaned
    assert "Status is success with verified." in cleaned


@pytest.mark.asyncio
async def test_tts_queue_sequential_delivery():
    """Verify queued speech is delivered sequentially."""
    provider = MockTTSProvider()
    tts = TTSManager(provider=provider)

    await tts.speak("First response.")
    await tts.speak("Second response.")

    # Allow worker loop to process queue
    await asyncio.sleep(0.3)

    assert "First response." in provider.spoken_history
    assert "Second response." in provider.spoken_history
    await tts.queue.stop()


@pytest.mark.asyncio
async def test_instant_interruption():
    """Verify interrupt() immediately flushes queue and sets provider interrupted state."""
    provider = MockTTSProvider()
    tts = TTSManager(provider=provider)

    await tts.queue.enqueue("Long monologue paragraph 1")
    await tts.queue.enqueue("Long monologue paragraph 2")

    tts.interrupt()

    assert tts.queue._queue.empty() is True
    assert provider._interrupted is True
    await tts.queue.stop()
