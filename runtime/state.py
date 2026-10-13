"""Runtime State Machine and Lifecycle States for R.I.O. (Milestone 5.x).

Manages the explicit daemon states:
STOPPED -> STARTING -> STANDBY -> AWAKING -> ACTIVE -> PROCESSING ->
EXECUTING -> VERIFYING -> RESPONDING -> ACTIVE (stays active!)
and STANDBY / PAUSED / SHUTTING_DOWN / ERROR.
"""

from datetime import datetime, timezone
from enum import Enum
import json
import logging
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional

from runtime.pidfile import get_data_dir

logger = logging.getLogger("rio.runtime.state")

DEFAULT_STATE_FILE = get_data_dir() / "runtime_state.json"


class RuntimeState(str, Enum):
    """Lifecycle state machine for R.I.O. persistent runtime."""
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    STANDBY = "STANDBY"
    AWAKING = "AWAKING"
    ACTIVE = "ACTIVE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    RESPONDING = "RESPONDING"
    MONITORING = "MONITORING"
    WAITING = "WAITING"
    SPEAKING = "SPEAKING"
    PAUSED = "PAUSED"
    SHUTTING_DOWN = "SHUTTING_DOWN"
    ERROR = "ERROR"


class RuntimeStateMachine:
    """Manages active runtime lifecycle state and transition events."""

    def __init__(self, initial_state: RuntimeState = RuntimeState.STOPPED, state_file: Optional[Path] = None):
        self._current_state = initial_state
        self._state_file = state_file or DEFAULT_STATE_FILE
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._last_transition_time = time.time()
        self._listeners: List[Callable[[RuntimeState, RuntimeState], Any]] = []
        self._active_task_info: Optional[str] = None
        self._error_message: Optional[str] = None
        self._persist_state()

    @property
    def current_state(self) -> RuntimeState:
        return self._current_state

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self._last_transition_time

    def register_listener(self, listener: Callable[[RuntimeState, RuntimeState], Any]) -> None:
        """Register a callback for state changes: (old_state, new_state) -> None."""
        self._listeners.append(listener)

    def transition_to(
        self,
        new_state: RuntimeState,
        task_info: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Transition runtime into new_state and notify listeners."""
        old_state = self._current_state
        if old_state == new_state and new_state != RuntimeState.ERROR:
            return True

        self._current_state = new_state
        self._last_transition_time = time.time()
        if task_info is not None:
            self._active_task_info = task_info
        if error_message is not None:
            self._error_message = error_message

        logger.info(f"Runtime transition: {old_state.value} -> {new_state.value} (task: {self._active_task_info})")

        self._persist_state()

        for listener in self._listeners:
            try:
                listener(old_state, new_state)
            except Exception as e:
                logger.warning(f"Error in state transition listener: {e}")

        return True

    def _persist_state(self) -> None:
        """Persist state snapshot to disk."""
        try:
            payload = {
                "state": self._current_state.value,
                "timestamp": time.time(),
                "timestamp_iso": datetime.now(timezone.utc).isoformat(),
                "active_task": self._active_task_info,
                "error": self._error_message,
            }
            self._state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug(f"Could not persist runtime state to disk: {e}")

    @classmethod
    def read_persisted_state(cls, state_file: Optional[Path] = None) -> Dict[str, Any]:
        """Read saved runtime state snapshot."""
        target = state_file or DEFAULT_STATE_FILE
        if not target.exists():
            return {"state": RuntimeState.STOPPED.value}
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            return {"state": RuntimeState.STOPPED.value}
