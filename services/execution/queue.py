"""Priority Execution Queue & Task Identity Registry for R.I.O. (Milestone 5).

Manages pending and active tasks with priority weighting, duplicate task detection,
and state lifecycle tracking.
"""

import asyncio
from datetime import datetime, timezone
from enum import Enum
import logging
import time
from typing import Any, Dict, List, Optional
import uuid

from packages.schemas.tasks import Task, TaskStatus

logger = logging.getLogger("rio.execution.queue")


class TaskPriority(str, Enum):
    CRITICAL = "critical"      # Weight: 4
    HIGH = "high"              # Weight: 3
    NORMAL = "normal"          # Weight: 2
    LOW = "low"                # Weight: 1
    BACKGROUND = "background"  # Weight: 0


PRIORITY_WEIGHTS = {
    TaskPriority.CRITICAL: 4,
    TaskPriority.HIGH: 3,
    TaskPriority.NORMAL: 2,
    TaskPriority.LOW: 1,
    TaskPriority.BACKGROUND: 0,
}


class ExecutionQueue:
    """Fair, priority-aware execution queue with duplicate task detection."""

    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._task_priorities: Dict[str, TaskPriority] = {}
        self._active_goals: Dict[str, str] = {}  # goal_hash -> task_id

    def register_task(self, task: Task, priority: TaskPriority = TaskPriority.NORMAL) -> Task:
        """Register a task into the queue and index its goal for duplicate prevention."""
        self._tasks[task.id] = task
        self._task_priorities[task.id] = priority

        norm_goal = task.goal.strip().lower()
        self._active_goals[norm_goal] = task.id
        return task

    def find_active_duplicate(self, goal: str) -> Optional[Task]:
        """Check if an equivalent task is currently pending or running."""
        norm_goal = goal.strip().lower()
        existing_id = self._active_goals.get(norm_goal)
        if existing_id and existing_id in self._tasks:
            t = self._tasks[existing_id]
            if t.status in (TaskStatus.PENDING, TaskStatus.PLANNING, TaskStatus.RUNNING, TaskStatus.WAITING_APPROVAL):
                return t
        return None

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def mark_completed(self, task_id: str, status: TaskStatus = TaskStatus.COMPLETED) -> None:
        """Mark task lifecycle complete and clean up active goal index."""
        if task_id in self._tasks:
            t = self._tasks[task_id]
            t.status = status
            t.completed_at = datetime.now(timezone.utc).isoformat()
            norm_goal = t.goal.strip().lower()
            if self._active_goals.get(norm_goal) == task_id:
                self._active_goals.pop(norm_goal, None)

    def list_active_tasks(self) -> List[Task]:
        """Return all tasks that are currently active (pending, running, waiting)."""
        active_statuses = {TaskStatus.PENDING, TaskStatus.PLANNING, TaskStatus.RUNNING, TaskStatus.WAITING_APPROVAL}
        return [t for t in self._tasks.values() if t.status in active_statuses]
