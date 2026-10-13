"""Speech-To-Text (STT) Service for R.I.O. (Milestone 5.x).

Handles converting raw PCM speech buffers into standard WAV containers
and transcribing via Groq Whisper (whisper-large-v3-turbo) or Mock provider.
"""

import io
import logging
import os
from typing import Optional
import wave

from services.model_router.router import ModelRouter

logger = logging.getLogger("rio.voice.stt")


class STTService:
    """Encodes PCM audio and coordinates Speech-To-Text via Groq Whisper."""

    def __init__(self, model_router: Optional[ModelRouter] = None):
        self.model_router = model_router or ModelRouter()

    @staticmethod
    def pcm_to_wav(
        pcm_bytes: bytes,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,
    ) -> bytes:
        """Wrap raw PCM bytes in standard RIFF/WAVE container."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)
        return buf.getvalue()

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str = "en",
    ) -> str:
        """Transcribe audio bytes (WAV or PCM)."""
        if not audio_bytes:
            return ""

        # If audio is raw PCM without RIFF header, wrap it in WAV
        if not audio_bytes.startswith(b"RIFF"):
            audio_bytes = self.pcm_to_wav(audio_bytes)

        # In test mode, allow synthetic transcription bypass
        if os.getenv("RIO_ENV") == "test":
            # If explicit test transcription is injected in environment
            mock_text = os.getenv("MOCK_STT_TRANSCRIPTION")
            if mock_text is not None:
                return mock_text

        try:
            transcription = await self.model_router.transcribe(
                audio_bytes=audio_bytes,
                language=language,
            )
            return (transcription or "").strip()
        except Exception as e:
            logger.warning(f"Groq Whisper transcription failed: {e}. Falling back to empty text.")
            return ""
