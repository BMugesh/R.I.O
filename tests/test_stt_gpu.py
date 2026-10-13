"""Test Local & Hybrid STT Service (Milestone 4)."""
import pytest
pytestmark = pytest.mark.gpu



import pytest
from services.inference.stt import SpeechToTextService, get_stt_service


@pytest.mark.asyncio
async def test_stt_transcription_local():
    service = get_stt_service()
    dummy_audio = b"RIFF" + b"\x00" * 16000

    text = await service.transcribe(dummy_audio, privacy="preferred_local")
    assert "Transcribed" in text
    assert "RIO" in text


@pytest.mark.asyncio
async def test_stt_transcription_privacy_local_only():
    service = get_stt_service()
    dummy_audio = b"RIFF" + b"\x00" * 16000

    text = await service.transcribe(dummy_audio, privacy="local_only", allow_remote=False)
    assert len(text) > 0
