"""Voice Activity Detection (VAD) Engine for R.I.O. (Milestone 5.x).

Calculates real-time acoustic energy (RMS) and silence duration
to accurately detect speech boundaries without cloud streaming.
"""

import logging
import math
import os
import struct
import time
from typing import List, Optional, Tuple

logger = logging.getLogger("rio.voice.vad")


class VoiceActivityDetector:
    """Detects speech onset and trailing silence using lightweight acoustic RMS."""

    def __init__(
        self,
        energy_threshold: float = 100.0,
        silence_timeout_ms: float = 700.0,
        max_utterance_ms: float = 10000.0,
        min_utterance_ms: float = 300.0,
        sample_rate: int = 16000,
        sample_width: int = 2,
    ):
        self.energy_threshold = float(os.getenv("RIO_VAD_ENERGY_THRESHOLD", str(energy_threshold)))
        self.silence_timeout_ms = float(os.getenv("RIO_VAD_SILENCE_MS", str(silence_timeout_ms)))
        self.max_utterance_ms = float(os.getenv("RIO_MAX_UTTERANCE_MS", str(max_utterance_ms)))
        self.min_utterance_ms = float(os.getenv("RIO_MIN_UTTERANCE_MS", str(min_utterance_ms)))
        self.sample_rate = sample_rate
        self.sample_width = sample_width

        self._in_speech: bool = False
        self._speech_start_time: Optional[float] = None
        self._last_speech_time: Optional[float] = None
        self._buffer: List[bytes] = []

    def calculate_rms(self, pcm_chunk: bytes) -> float:
        """Calculate Root Mean Square (RMS) energy of 16-bit PCM chunk."""
        if not pcm_chunk or len(pcm_chunk) < self.sample_width:
            return 0.0

        try:
            # 16-bit signed integer decoding
            count = len(pcm_chunk) // self.sample_width
            format_str = f"<{count}h"
            shorts = struct.unpack(format_str, pcm_chunk)
            sum_squares = sum(s * s for s in shorts)
            mean = sum_squares / count
            return math.sqrt(mean)
        except Exception:
            return 0.0

    def process_chunk(self, chunk: bytes) -> Tuple[bool, bool, float]:
        """Process incoming PCM chunk.
        
        Returns:
            (in_speech: bool, is_utterance_complete: bool, current_energy: float)
        """
        energy = self.calculate_rms(chunk)
        now = time.time()

        if energy >= self.energy_threshold:
            if not self._in_speech:
                self._in_speech = True
                self._speech_start_time = now
                self._buffer.clear()
            self._last_speech_time = now
            self._buffer.append(chunk)
            return True, False, energy

        # If energy is below threshold
        if self._in_speech:
            self._buffer.append(chunk)
            elapsed_ms = (now - self._speech_start_time) * 1000.0 if self._speech_start_time else 0.0
            silence_ms = (now - self._last_speech_time) * 1000.0 if self._last_speech_time else 0.0

            # Check if silence timeout reached or max utterance exceeded
            if silence_ms >= self.silence_timeout_ms or elapsed_ms >= self.max_utterance_ms:
                if elapsed_ms >= self.min_utterance_ms:
                    self._in_speech = False
                    return False, True, energy
                else:
                    # Utterance too short (e.g. noise click)
                    self.reset()
                    return False, False, energy

            return True, False, energy

        return False, False, energy

    def get_audio_bytes(self) -> bytes:
        """Retrieve collected PCM bytes for current utterance."""
        return b"".join(self._buffer)

    def reset(self) -> None:
        """Reset VAD state for next utterance."""
        self._in_speech = False
        self._speech_start_time = None
        self._last_speech_time = None
        self._buffer.clear()
