"""R.I.O. Voice & Wake-Word Subsystem (Milestone 3).

Provides always-on wake-word detection, local voice activity detection (VAD),
speech-to-text transcription via Groq Whisper, and unified orchestration dispatch.
"""

from voice.audio_capture import AudioBuffer, AudioCaptureEngine, AudioConfig
from voice.manager import VoiceManager
from voice.permissions import VoicePermissionManager
from voice.session import VoiceSession, VoiceState
from voice.transcription import TranscriptionService
from voice.wake_word import WakeWordDetector

__all__ = [
    "AudioBuffer",
    "AudioCaptureEngine",
    "AudioConfig",
    "VoiceManager",
    "VoicePermissionManager",
    "VoiceSession",
    "VoiceState",
    "TranscriptionService",
    "WakeWordDetector",
]
