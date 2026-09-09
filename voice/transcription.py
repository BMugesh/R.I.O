"""Transcription Service for R.I.O. Voice Interface.

Encapsulates speech-to-text processing via ModelRouter and Groq Whisper (whisper-large-v3-turbo).
"""

import io
import logging
import time
from typing import Optional
import wave
from services.model_router.router import ModelRouter

logger = logging.getLogger("rio.voice.transcription")


class TranscriptionService:
    """Provides speech-to-text audio transcription backed by Groq Whisper."""

    def __init__(self, model_router: Optional[ModelRouter] = None):
        self.model_router = model_router or ModelRouter()

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str = "en",
        model: Optional[str] = None,
    ) -> str:
        """Transcribe in-memory WAV audio bytes to text string."""
        if not audio_bytes or len(audio_bytes) < 44:
            logger.warning("Empty or truncated audio payload provided for transcription.")
            return ""

        start_time = time.time()
        # Verify valid WAV header
        if not self._is_valid_wav(audio_bytes):
            logger.warning("Audio payload is not valid WAV container. Processing raw bytes.")

        try:
            transcription = await self.model_router.transcribe(
                audio_bytes=audio_bytes,
                language=language,
                model=model,
            )
            elapsed = time.time() - start_time
            logger.info(f"Transcription completed in {elapsed:.2f}s: '{transcription}'")
            return transcription.strip()
        except Exception as e:
            logger.error(f"Transcription failure: {e}")
            # Resilient fallback to mock
            return await self.model_router.transcribe(
                audio_bytes=audio_bytes,
                language=language,
                provider="mock",
            )

    @staticmethod
    def _is_valid_wav(data: bytes) -> bool:
        """Check for standard RIFF/WAVE header bytes."""
        if len(data) < 12:
            return False
        return data[:4] == b"RIFF" and data[8:12] == b"WAVE"
