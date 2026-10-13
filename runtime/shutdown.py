"""Graceful Shutdown Coordinator for R.I.O. Runtime (Milestone 5.x).

Handles clean teardown of all runtime resources:
- Signals shutdown event
- Stops audio and wake-word listener
- Stops and flushes TTS queue
- Cleans up active asyncio tasks
- Releases GPU resources and workers
- Flushes logs and removes PID file
"""

import asyncio
import logging
import os
from pathlib import Path
import sys
from typing import Any, Callable, List, Optional
from runtime.pidfile import PIDManager
from runtime.state import RuntimeState, RuntimeStateMachine

logger = logging.getLogger("rio.runtime.shutdown")


class RuntimeShutdownHandler:
    """Manages deterministic and leak-free shutdown sequences."""

    def __init__(
        self,
        state_machine: Optional[RuntimeStateMachine] = None,
        pid_manager: Optional[PIDManager] = None,
    ):
        self.state_machine = state_machine or RuntimeStateMachine()
        self.pid_manager = pid_manager or PIDManager()
        self._cleanup_hooks: List[Callable[[], Any]] = []
        self._is_shutting_down = False
        self._shutdown_event = asyncio.Event()

    def register_cleanup_hook(self, hook: Callable[[], Any]) -> None:
        """Register a synchronous or asynchronous hook to execute during shutdown."""
        self._cleanup_hooks.append(hook)

    @property
    def is_shutting_down(self) -> bool:
        return self._is_shutting_down

    @property
    def shutdown_event(self) -> asyncio.Event:
        return self._shutdown_event

    def request_shutdown(self, reason: str = "User requested") -> None:
        """Trigger the shutdown event."""
        if self._is_shutting_down:
            return
        self._is_shutting_down = True
        logger.info(f"Shutdown requested: {reason}")
        self.state_machine.transition_to(RuntimeState.SHUTTING_DOWN)
        self._shutdown_event.set()

    async def execute_shutdown(self) -> None:
        """Execute all cleanup hooks and finalize daemon termination."""
        logger.info("Executing graceful R.I.O. runtime shutdown sequence...")
        self.state_machine.transition_to(RuntimeState.SHUTTING_DOWN)

        # 1. Run registered cleanup hooks (reverse order)
        for hook in reversed(self._cleanup_hooks):
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook()
                else:
                    res = hook()
                    if asyncio.iscoroutine(res):
                        await res
            except Exception as e:
                logger.warning(f"Error executing shutdown hook {hook}: {e}")

        # 2. Release GPU resources if ComputeRouter / PyTorch is loaded
        try:
            from services.compute.router import get_compute_router
            router = get_compute_router()
            if hasattr(router, "cleanup"):
                await router.cleanup()
        except Exception:
            pass

        # 3. Release Test Governor / Resource tracker if active
        try:
            from services.test_governor.cleanup import ResourceCleanupDispatcher
            await ResourceCleanupDispatcher.cleanup_all()
        except Exception:
            pass

        # 4. Remove PID file and mark state STOPPED
        self.pid_manager.remove_pid()
        self.state_machine.transition_to(RuntimeState.STOPPED)
        logger.info("R.I.O. Runtime shutdown complete. State: STOPPED.")
