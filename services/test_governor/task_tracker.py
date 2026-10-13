"""Asyncio Task Tracker and Teardown Manager (Milestone 4.5).

Tracks background coroutines and tasks created during test execution,
ensuring graceful cancellation and awaiting to eliminate asyncio task leaks.
"""

import asyncio
import logging
from typing import List, Optional, Set

logger = logging.getLogger("rio.test_governor.task")


class TaskTracker:
    """Tracks and tears down test-scoped asyncio tasks."""

    def __init__(self):
        self._registered_tasks: Set[asyncio.Task] = set()
        self._baseline_task_names: Set[str] = set()

    def capture_baseline(self) -> None:
        """Capture active task names in current running event loop."""
        try:
            loop = asyncio.get_running_loop()
            tasks = asyncio.all_tasks(loop)
            self._baseline_task_names = {t.get_name() for t in tasks}
        except RuntimeError:
            self._baseline_task_names = set()

    def register_task(self, task: asyncio.Task) -> None:
        """Explicitly register an asyncio task for lifecycle management."""
        self._registered_tasks.add(task)

    def get_lingering_tasks(self) -> List[asyncio.Task]:
        """Return tasks that are still pending/alive."""
        lingering = []
        try:
            loop = asyncio.get_running_loop()
            current_tasks = asyncio.all_tasks(loop)
            current_self = asyncio.current_task(loop)

            for t in current_tasks:
                if t is current_self:
                    continue
                if t in self._registered_tasks and not t.done():
                    lingering.append(t)
                elif t.get_name() not in self._baseline_task_names and not t.done():
                    lingering.append(t)
        except RuntimeError:
            # Check registered tasks only
            for t in self._registered_tasks:
                if not t.done():
                    lingering.append(t)

        return lingering

    async def cleanup_tasks(self, timeout: float = 0.5) -> List[str]:
        """Cancel and await all lingering tasks. Returns names of cancelled tasks."""
        lingering = self.get_lingering_tasks()
        if not lingering:
            return []

        cancelled_names = []
        for t in lingering:
            cancelled_names.append(t.get_name())
            t.cancel()

        try:
            await asyncio.wait_for(
                asyncio.gather(*lingering, return_exceptions=True),
                timeout=timeout,
            )
        except (asyncio.TimeoutError, Exception) as e:
            logger.debug(f"Task cancellation wait note: {e}")

        self._registered_tasks.clear()
        return cancelled_names
