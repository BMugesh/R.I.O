"""Voice & Speech Router (STT & TTS)."""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from apps.api.deps import Container, get_container

router = APIRouter(prefix="/voice", tags=["Voice"])


@router.post("/transcribe")
async def transcribe_speech(
    file: UploadFile = File(...),
    language: str = Form("en"),
    container: Container = Depends(get_container),
):
    """Transcribe user microphone audio to text via Groq Whisper."""
    audio_bytes = await file.read()
    transcription = await container.model_router.transcribe(
        audio_bytes=audio_bytes,
        language=language,
    )
    return {"text": transcription}


@router.post("/synthesize")
async def synthesize_speech(text: str, container: Container = Depends(get_container)):
    """Text-to-speech synthesis endpoint placeholder."""
    return {"status": "success", "audio_url": None, "text": text}
