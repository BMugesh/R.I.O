"""Voice Session State Machine for R.I.O.

Manages the lifecycle states of voice interaction:
IDLE -> LISTENING -> WAKE_DETECTED -> CAPTURING -> TRANSCRIBING -> PROCESSING -> IDLE
"""

from datetime import datetime, timezone
from enum import Enum
import logging
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

logger = logging.getLogger("rio.voice.session")


class VoiceState(str, Enum):
    """Lifecycle states for voice wake-word and speech processing."""
    IDLE = "idle"
    LISTENING = "listening"
    WAKE_DETECTED = "wake_detected"
    CAPTURING = "capturing"
    TRANSCRIBING = "transcribing"
    PROCESSING = "processing"
    ERROR = "error"


class VoiceSession:
    """Tracks state, timing, audio metrics, and transitions of a single voice interaction."""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id: str = session_id or f"voice_{uuid.uuid4().hex[:8]}"
        self.state: VoiceState = VoiceState.IDLE
        self.started_at: datetime = datetime.now(timezone.utc)
        self.last_transition_at: datetime = self.started_at

        # Interaction metrics & artifacts
        self.wake_word_detected: Optional[str] = None
        self.wake_word_timestamp: Optional[float] = None
        self.raw_audio_chunks: List[bytes] = []
        self.audio_bytes_length: int = 0
        self.audio_duration_seconds: float = 0.0
        self.transcribed_text: Optional[str] = None
        self.command_text: Optional[str] = None
        self.orchestrator_reply: Optional[str] = None
        self.last_error: Optional[str] = None

        self._state_callbacks: List[Callable[[VoiceState, VoiceState], Any]] = []

    def register_callback(self, callback: Callable[[VoiceState, VoiceState], Any]) -> None:
        """Register a callback function for state transitions: (old_state, new_state) -> None."""
        self._state_callbacks.append(callback)

    def transition_to(self, new_state: VoiceState, error_message: Optional[str] = None) -> None:
        """Perform a valid state transition and notify registered listeners."""
        old_state = self.state
        if old_state == new_state and new_state != VoiceState.ERROR:
            return

        self.state = new_state
        self.last_transition_at = datetime.now(timezone.utc)
        if error_message:
            self.last_error = error_message
            logger.error(f"[VoiceSession {self.session_id}] Error state transition: {error_message}")
        else:
            logger.info(f"[VoiceSession {self.session_id}] State changed: {old_state.value} -> {new_state.value}")

        for cb in self._state_callbacks:
            try:
                cb(old_state, new_state)
            except Exception as ex:
                logger.warning(f"Error executing voice state callback: {ex}")

    def reset_for_listening(self) -> None:
        """Reset session buffer back to LISTENING state."""
        self.wake_word_detected = None
        self.wake_word_timestamp = None
        self.raw_audio_chunks = []
        self.audio_bytes_length = 0
        self.audio_duration_seconds = 0.0
        self.transcribed_text = None
        self.command_text = None
        self.orchestrator_reply = None
        self.last_error = None
        self.transition_to(VoiceState.LISTENING)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session telemetry."""
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "wake_word": self.wake_word_detected,
            "audio_duration": self.audio_duration_seconds,
            "audio_bytes": self.audio_bytes_length,
            "transcribed_text": self.transcribed_text,
            "command_text": self.command_text,
            "reply": self.orchestrator_reply,
            "error": self.last_error,
            "started_at": self.started_at.isoformat(),
            "updated_at": self.last_transition_at.isoformat(),
        }
