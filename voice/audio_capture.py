"""Audio Capture Engine and Audio Utilities for R.I.O.

Handles in-memory PCM buffering, RMS energy calculation for VAD (Voice Activity Detection),
WAV container packaging, and synthetic audio generation for testing.
"""

import io
import logging
import math
import struct
from typing import List, Optional, Tuple
import wave

logger = logging.getLogger("rio.voice.audio_capture")


class AudioConfig:
    """Standard audio capture parameters."""
    SAMPLE_RATE: int = 16000  # 16 kHz standard for Whisper STT
    CHANNELS: int = 1        # Mono audio
    SAMPLE_WIDTH: int = 2    # 16-bit PCM (2 bytes per sample)
    CHUNK_SIZE: int = 1024   # Samples per chunk
    ENERGY_THRESHOLD: float = 300.0  # RMS threshold for voice presence
    SILENCE_LIMIT_CHUNKS: int = 15   # ~1 second of consecutive silence to end utterance


class AudioBuffer:
    """Collects raw audio chunks and computes real-time acoustic energy."""

    def __init__(self, config: Optional[AudioConfig] = None):
        self.config = config or AudioConfig()
        self.chunks: List[bytes] = []
        self.total_bytes: int = 0
        self.silent_chunks_count: int = 0

    def add_chunk(self, chunk: bytes) -> float:
        """Append raw PCM chunk and return its RMS energy."""
        self.chunks.append(chunk)
        self.total_bytes += len(chunk)
        energy = self.calculate_rms(chunk)

        if energy < self.config.ENERGY_THRESHOLD:
            self.silent_chunks_count += 1
        else:
            self.silent_chunks_count = 0

        return energy

    def is_silence_detected(self) -> bool:
        """Check if silence has exceeded the utterance termination limit."""
        return self.silent_chunks_count >= self.config.SILENCE_LIMIT_CHUNKS

    def calculate_rms(self, chunk: bytes) -> float:
        """Calculate Root Mean Square (RMS) energy level of 16-bit PCM chunk."""
        if not chunk or len(chunk) < 2:
            return 0.0

        count = len(chunk) // 2
        shorts = struct.unpack(f"{count}h", chunk[:count * 2])
        sum_squares = sum(s * s for s in shorts)
        mean_square = sum_squares / count
        return math.sqrt(mean_square)

    def duration_seconds(self) -> float:
        """Calculate total audio duration in seconds."""
        bytes_per_second = self.config.SAMPLE_RATE * self.config.CHANNELS * self.config.SAMPLE_WIDTH
        if bytes_per_second == 0:
            return 0.0
        return self.total_bytes / bytes_per_second

    def to_wav_bytes(self) -> bytes:
        """Encode buffered PCM chunks into a valid in-memory WAV container."""
        pcm_data = b"".join(self.chunks)
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wav_file:
            wav_file.setnchannels(self.config.CHANNELS)
            wav_file.setsampwidth(self.config.SAMPLE_WIDTH)
            wav_file.setframerate(self.config.SAMPLE_RATE)
            wav_file.writeframes(pcm_data)
        return wav_io.getvalue()

    def clear(self) -> None:
        """Reset buffer."""
        self.chunks.clear()
        self.total_bytes = 0
        self.silent_chunks_count = 0


class AudioCaptureEngine:
    """Audio capture engine managing recording, chunk processing, and synthesis."""

    def __init__(self, config: Optional[AudioConfig] = None):
        self.config = config or AudioConfig()
        self.buffer = AudioBuffer(self.config)
        self.is_capturing: bool = False

    def start_capture(self) -> None:
        """Start or reset active audio capture buffer."""
        self.buffer.clear()
        self.is_capturing = True
        logger.info("Audio capture engine started.")

    def stop_capture(self) -> bytes:
        """Stop capture and return complete encoded WAV audio bytes."""
        self.is_capturing = False
        wav_bytes = self.buffer.to_wav_bytes()
        logger.info(f"Audio capture stopped. Buffer size: {self.buffer.total_bytes} bytes ({self.buffer.duration_seconds():.2f}s).")
        return wav_bytes

    def feed_chunk(self, chunk: bytes) -> Tuple[float, bool]:
        """Feed PCM chunk to active buffer. Returns (energy, is_silence_limit_reached)."""
        if not self.is_capturing:
            return 0.0, False
        energy = self.buffer.add_chunk(chunk)
        silence_reached = self.buffer.is_silence_detected()
        return energy, silence_reached

    @staticmethod
    def generate_synthetic_tone(
        frequency: float = 440.0,
        duration: float = 1.0,
        sample_rate: int = 16000,
        amplitude: float = 0.5,
    ) -> bytes:
        """Generate synthetic sinusoidal 16-bit PCM audio bytes for offline testing."""
        num_samples = int(sample_rate * duration)
        raw_pcm = bytearray()
        for i in range(num_samples):
            t = float(i) / sample_rate
            sample = int(amplitude * 32767.0 * math.sin(2.0 * math.pi * frequency * t))
            sample = max(-32768, min(32767, sample))
            raw_pcm.extend(struct.pack("<h", sample))

        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(raw_pcm)
        return wav_io.getvalue()
