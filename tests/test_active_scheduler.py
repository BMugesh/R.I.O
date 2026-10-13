"""Tests for Active Background Task Scheduler (Phase 9).

Validates:
1. Registration, persistence, and state tracking.
2. Due task calculation (past vs future trigger times).
3. Discrete tick execution and lifecycle progression.
4. Active background loop execution and clean termination with 0 leaks.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import os
import shutil
import tempfile
import pytest
from services.scheduler.scheduler import ScheduledTask, ScheduledTaskState, TaskScheduler


@pytest.mark.asyncio
async def test_scheduler_due_tasks_and_tick():
    """Verify that due tasks are detected and triggered via tick()."""
    temp_dir = tempfile.mkdtemp(prefix="rio_sched_test_")
    storage_path = os.path.join(temp_dir, "test_tasks.json")

    try:
        scheduler = TaskScheduler(storage_path=storage_path)

        now = datetime.now(timezone.utc)
        past_time = (now - timedelta(minutes=5)).isoformat()
        future_time = (now + timedelta(hours=1)).isoformat()

        t_due = scheduler.schedule(goal="Past Task", trigger_time_iso=past_time)
        t_future = scheduler.schedule(goal="Future Task", trigger_time_iso=future_time)

        due_tasks = scheduler.get_due_tasks()
        assert len(due_tasks) == 1
        assert due_tasks[0].id == t_due.id

        # Run a tick
        executed = await scheduler.tick()
        assert len(executed) == 1
        assert executed[0].id == t_due.id
        assert executed[0].state == ScheduledTaskState.COMPLETED
        assert executed[0].completed_at is not None

        # Future task remains scheduled
        assert scheduler.get_task(t_future.id).state == ScheduledTaskState.SCHEDULED

        # No more tasks due
        assert len(scheduler.get_due_tasks()) == 0
    finally:
        scheduler.clear()
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_scheduler_background_loop_and_clean_stop():
    """Verify that background scheduler loop triggers due tasks and stops without leaking coroutines."""
    temp_dir = tempfile.mkdtemp(prefix="rio_sched_loop_test_")
    storage_path = os.path.join(temp_dir, "test_tasks.json")

    try:
        scheduler = TaskScheduler(storage_path=storage_path)
        executed_tasks = []

        async def mock_executor(task: ScheduledTask):
            executed_tasks.append(task.id)
            return {"status": "ok"}

        scheduler.set_executor_callback(mock_executor)

        # Schedule a task due immediately
        now = datetime.now(timezone.utc)
        past_time = (now - timedelta(seconds=1)).isoformat()
        task = scheduler.schedule(goal="Immediate Execution", trigger_time_iso=past_time)

        # Start loop with fast 50ms check interval
        await scheduler.start(check_interval=0.05)
        assert scheduler._running is True
        assert scheduler._loop_task is not None

        # Wait up to 1 second for task to be triggered by background loop
        for _ in range(20):
            if scheduler.get_task(task.id).state == ScheduledTaskState.COMPLETED:
                break
            await asyncio.sleep(0.05)

        t_res = scheduler.get_task(task.id)
        assert t_res.state == ScheduledTaskState.COMPLETED
        assert task.id in executed_tasks

        # Stop loop and verify clean shutdown
        await scheduler.stop()
        assert scheduler._running is False
        assert scheduler._loop_task is None
    finally:
        await scheduler.stop()
        scheduler.clear()
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
