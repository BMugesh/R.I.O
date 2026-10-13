"""Persistent Voice Session State for R.I.O. (Milestone 5.x).

Tracks the ongoing voice interaction lifecycle and turn telemetry.
"""

from datetime import datetime, timezone
from enum import Enum
import logging
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

logger = logging.getLogger("rio.voice.session")


class VoiceSessionState(str, Enum):
    """Lifecycle states of the voice conversation."""
    STANDBY = "STANDBY"
    AWAKING = "AWAKING"
    ACTIVE = "ACTIVE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    RESPONDING = "RESPONDING"
    ERROR = "ERROR"


class VoiceSession:
    """Represents an active multi-turn voice interaction session."""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id: str = session_id or f"vsession_{uuid.uuid4().hex[:8]}"
        self.state: VoiceSessionState = VoiceSessionState.STANDBY
        self.created_at: float = time.time()
        self.last_activity: float = self.created_at

        self.turns_count: int = 0
        self.wake_phrase_detected: Optional[str] = None
        self.last_user_text: Optional[str] = None
        self.last_assistant_response: Optional[str] = None
        self.last_error: Optional[str] = None

        self._callbacks: List[Callable[[VoiceSessionState, VoiceSessionState], Any]] = []

    def register_callback(self, callback: Callable[[VoiceSessionState, VoiceSessionState], Any]) -> None:
        self._callbacks.append(callback)

    def transition_to(self, new_state: VoiceSessionState, error: Optional[str] = None) -> None:
        old_state = self.state
        if old_state == new_state and new_state != VoiceSessionState.ERROR:
            return

        self.state = new_state
        self.last_activity = time.time()
        if error:
            self.last_error = error

        for cb in self._callbacks:
            try:
                cb(old_state, new_state)
            except Exception as e:
                logger.warning(f"VoiceSession callback error: {e}")

    def record_turn(self, user_text: str, assistant_response: str) -> None:
        self.turns_count += 1
        self.last_user_text = user_text
        self.last_assistant_response = assistant_response
        self.last_activity = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "turns_count": self.turns_count,
            "wake_phrase_detected": self.wake_phrase_detected,
            "last_user_text": self.last_user_text,
            "last_assistant_response": self.last_assistant_response,
            "uptime_seconds": time.time() - self.created_at,
            "last_activity_seconds_ago": time.time() - self.last_activity,
        }
