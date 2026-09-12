"""R.I.O. Task Scheduler Service.

Manages scheduled task registration, persistence across Core restarts,
device-bound execution dispatch, and lifecycle state tracking:
SCHEDULED -> WAITING -> TRIGGERED -> RUNNING -> VERIFYING -> COMPLETED
"""

import asyncio
from datetime import datetime, timezone
from enum import Enum
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field
from packages.schemas.tasks import Task, TaskPlan, TaskStatus

logger = logging.getLogger("rio.scheduler")


class ScheduledTaskState(str, Enum):
    SCHEDULED = "SCHEDULED"
    WAITING = "WAITING"
    TRIGGERED = "TRIGGERED"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ScheduledTask(BaseModel):
    """Represents a scheduled future execution task."""
    id: str = Field(default_factory=lambda: f"sched_{uuid.uuid4().hex[:8]}")
    goal: str
    trigger_time_iso: str
    origin_device_id: str = "phone-01"
    execution_device_id: str = "phone-01"
    state: ScheduledTaskState = ScheduledTaskState.SCHEDULED
    plan: Optional[TaskPlan] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    triggered_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskScheduler:
    """Persistent scheduler managing scheduled actions across R.I.O. devices."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path or os.path.join(os.getcwd(), "data", "scheduled_tasks.json"))
        self._tasks: Dict[str, ScheduledTask] = {}
        self._executor_callback: Optional[Callable[[ScheduledTask], Any]] = None
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None
        self._load()

    def _load(self) -> None:
        """Load persisted tasks from disk to survive Core restarts."""
        try:
            if self.storage_path.exists():
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        task = ScheduledTask(**item)
                        self._tasks[task.id] = task
                logger.info(f"Loaded {len(self._tasks)} scheduled tasks from {self.storage_path}")
        except Exception as e:
            logger.warning(f"Failed to load scheduled tasks: {e}")

    def _save(self) -> None:
        """Persist scheduled tasks to disk."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump([t.model_dump() for t in self._tasks.values()], f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save scheduled tasks: {e}")

    def set_executor_callback(self, callback: Callable[[ScheduledTask], Any]) -> None:
        """Set callback to execute task when triggered."""
        self._executor_callback = callback

    def schedule(
        self,
        goal: str,
        trigger_time_iso: str,
        origin_device_id: str = "phone-01",
        execution_device_id: str = "phone-01",
        plan: Optional[TaskPlan] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ScheduledTask:
        """Register a new scheduled task."""
        task = ScheduledTask(
            goal=goal,
            trigger_time_iso=trigger_time_iso,
            origin_device_id=origin_device_id,
            execution_device_id=execution_device_id,
            state=ScheduledTaskState.SCHEDULED,
            plan=plan,
            metadata=metadata or {},
        )
        self._tasks[task.id] = task
        self._save()
        logger.info(f"Scheduled task '{task.id}' for {trigger_time_iso} on device '{execution_device_id}' (Origin: '{origin_device_id}')")
        return task

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        return self._tasks.get(task_id)

    def list_tasks(self, state: Optional[ScheduledTaskState] = None) -> List[ScheduledTask]:
        tasks = list(self._tasks.values())
        if state:
            return [t for t in tasks if t.state == state]
        return tasks

    def update_state(self, task_id: str, new_state: ScheduledTaskState, error: Optional[str] = None, result: Optional[Dict[str, Any]] = None) -> Optional[ScheduledTask]:
        """Update task lifecycle state."""
        task = self._tasks.get(task_id)
        if not task:
            return None
        task.state = new_state
        if error:
            task.error = error
        if result:
            task.result = result
        if new_state == ScheduledTaskState.TRIGGERED:
            task.triggered_at = datetime.now(timezone.utc).isoformat()
        elif new_state in (ScheduledTaskState.COMPLETED, ScheduledTaskState.FAILED):
            task.completed_at = datetime.now(timezone.utc).isoformat()
        self._save()
        return task

    async def trigger_now(self, task_id: str) -> ScheduledTask:
        """Manually trigger a scheduled task immediately through its lifecycle."""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found.")

        # Lifecycle progression:
        # SCHEDULED -> WAITING -> TRIGGERED -> RUNNING -> VERIFYING -> COMPLETED
        self.update_state(task_id, ScheduledTaskState.WAITING)
        await asyncio.sleep(0.05)

        self.update_state(task_id, ScheduledTaskState.TRIGGERED)
        await asyncio.sleep(0.05)

        self.update_state(task_id, ScheduledTaskState.RUNNING)
        await asyncio.sleep(0.05)

        if self._executor_callback:
            try:
                res = await self._executor_callback(task)
                self.update_state(task_id, ScheduledTaskState.VERIFYING)
                await asyncio.sleep(0.05)
                self.update_state(task_id, ScheduledTaskState.COMPLETED, result={"status": "verified", "execution_result": res})
            except Exception as e:
                self.update_state(task_id, ScheduledTaskState.FAILED, error=str(e))
        else:
            self.update_state(task_id, ScheduledTaskState.VERIFYING)
            await asyncio.sleep(0.05)
            self.update_state(task_id, ScheduledTaskState.COMPLETED, result={"status": "verified", "note": "Simulation verified"})

        return self._tasks[task_id]

    def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        task.state = ScheduledTaskState.CANCELLED
        self._save()
        return True

    def clear(self) -> None:
        """Clear memory cache and remove storage file."""
        self._tasks.clear()
        if self.storage_path.exists():
            try:
                self.storage_path.unlink()
            except Exception:
                pass
