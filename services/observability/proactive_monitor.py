"""Proactive Event Monitor for R.I.O. (Rule 34 & 35).

Monitors important system, build, process, and battery events using deterministic
local telemetry hooks without continuous remote LLM polling.
"""

import asyncio
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Set

import psutil

from runtime.event_listener import EventListener, RuntimeEvent

logger = logging.getLogger("rio.observability.proactive")


class ProactiveSuggestion:
    """A concise, actionable proactive suggestion for the user."""

    def __init__(
        self,
        event_type: str,
        message: str,
        action_payload: Optional[Dict[str, Any]] = None,
        severity: str = "info",
    ):
        self.event_type = event_type
        self.message = message
        self.action_payload = action_payload or {}
        self.severity = severity
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "message": self.message,
            "action_payload": self.action_payload,
            "severity": self.severity,
            "timestamp": self.timestamp,
        }


class ProactiveMonitor:
    """Monitors local host events deterministically and delivers concise proactive assistance."""

    def __init__(
        self,
        event_listener: Optional[EventListener] = None,
        check_interval: float = 1.0,
    ):
        self.event_listener = event_listener or EventListener()
        self.check_interval = check_interval
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

        # Watched targets
        self._watched_pids: Dict[int, Dict[str, Any]] = {}
        self._watched_files: Dict[str, Dict[str, Any]] = {}
        self._last_battery_warning_time: float = 0.0
        self._last_memory_warning_time: float = 0.0

        # Suggestion handler callback (e.g. voice/TTS or notification tray)
        self._suggestion_handlers: List[Callable[[ProactiveSuggestion], Any]] = []

    def register_suggestion_handler(self, handler: Callable[[ProactiveSuggestion], Any]) -> None:
        """Register a callback for proactive suggestions."""
        self._suggestion_handlers.append(handler)

    def watch_process(self, pid: int, label: str = "process", notify_on_exit: bool = True) -> None:
        """Watch a process (e.g. build, compile, training) for termination."""
        self._watched_pids[pid] = {
            "label": label,
            "notify_on_exit": notify_on_exit,
            "start_time": time.time(),
        }

    def unwatch_process(self, pid: int) -> None:
        self._watched_pids.pop(pid, None)

    def watch_file(self, file_path: str, label: str = "download", target_size: Optional[int] = None) -> None:
        """Watch a file for creation or complete download."""
        self._watched_files[str(Path(file_path).resolve())] = {
            "label": label,
            "target_size": target_size,
            "added_time": time.time(),
            "last_size": -1,
            "stable_checks": 0,
        }

    def unwatch_file(self, file_path: str) -> None:
        self._watched_files.pop(str(Path(file_path).resolve()), None)

    async def start(self) -> None:
        """Start the deterministic background monitor loop."""
        if self._running:
            return
        self._running = True
        self._monitor_task = asyncio.create_task(self._loop(), name="rio_proactive_monitor")
        logger.info("ProactiveMonitor started.")

    async def stop(self) -> None:
        """Stop monitor loop cleanly with 0 leaked tasks."""
        self._running = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        self._monitor_task = None
        logger.info("ProactiveMonitor stopped.")

    async def tick(self) -> List[ProactiveSuggestion]:
        """Execute a single deterministic evaluation pass over local system telemetry."""
        suggestions: List[ProactiveSuggestion] = []

        # 1. Process Lifecycle Checks
        dead_pids: List[int] = []
        for pid, info in list(self._watched_pids.items()):
            if not psutil.pid_exists(pid):
                dead_pids.append(pid)
                label = info.get("label", "Process")
                suggestion = ProactiveSuggestion(
                    event_type="proactive.process_exit",
                    message=f"{label} (PID {pid}) has finished executing.",
                    action_payload={"pid": pid, "label": label},
                    severity="info",
                )
                suggestions.append(suggestion)
                await self.event_listener.emit(
                    RuntimeEvent("proactive.process_exit", payload={"pid": pid, "label": label})
                )

        for pid in dead_pids:
            self._watched_pids.pop(pid, None)

        # 2. File & Download Completion Checks
        completed_files: List[str] = []
        for path_str, finfo in list(self._watched_files.items()):
            p = Path(path_str)
            if p.exists() and p.is_file():
                current_size = p.stat().st_size
                target_size = finfo.get("target_size")
                if target_size and current_size >= target_size:
                    completed_files.append(path_str)
                    sug = ProactiveSuggestion(
                        event_type="proactive.download_completed",
                        message=f"{finfo.get('label', 'File')} download completed: {p.name}.",
                        action_payload={"path": path_str, "size_bytes": current_size},
                        severity="info",
                    )
                    suggestions.append(sug)
                    await self.event_listener.emit(
                        RuntimeEvent("proactive.download_completed", payload={"path": path_str, "size_bytes": current_size})
                    )
                elif finfo["last_size"] == current_size and current_size > 0:
                    finfo["stable_checks"] += 1
                    # If size hasn't changed for 2 ticks and no .crdownload/.part extension
                    if finfo["stable_checks"] >= 2 and not path_str.endswith((".crdownload", ".part", ".tmp")):
                        completed_files.append(path_str)
                        sug = ProactiveSuggestion(
                            event_type="proactive.download_completed",
                            message=f"{finfo.get('label', 'File')} download complete: {p.name}.",
                            action_payload={"path": path_str, "size_bytes": current_size},
                            severity="info",
                        )
                        suggestions.append(sug)
                        await self.event_listener.emit(
                            RuntimeEvent("proactive.download_completed", payload={"path": path_str, "size_bytes": current_size})
                        )
                else:
                    finfo["last_size"] = current_size
                    finfo["stable_checks"] = 0

        for path_str in completed_files:
            self._watched_files.pop(path_str, None)

        # 3. Battery Telemetry Check
        now = time.time()
        if now - self._last_battery_warning_time > 300:  # Warn at most once every 5 minutes
            battery = psutil.sensors_battery()
            if battery and not battery.power_plugged and battery.percent <= 20:
                self._last_battery_warning_time = now
                sug = ProactiveSuggestion(
                    event_type="proactive.low_battery",
                    message=f"Battery is low ({battery.percent}%). Consider connecting to power.",
                    action_payload={"percent": battery.percent, "power_plugged": False},
                    severity="warning",
                )
                suggestions.append(sug)
                await self.event_listener.emit(
                    RuntimeEvent("proactive.low_battery", payload={"percent": battery.percent})
                )

        # 4. Dispatch suggestions to handlers
        for suggestion in suggestions:
            for handler in self._suggestion_handlers:
                try:
                    res = handler(suggestion)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as e:
                    logger.error(f"Error in proactive suggestion handler: {e}")

        return suggestions

    async def _loop(self) -> None:
        """Internal background polling loop."""
        while self._running:
            try:
                await self.tick()
            except Exception as e:
                logger.error(f"Error in proactive monitor tick: {e}")
            await asyncio.sleep(self.check_interval)
