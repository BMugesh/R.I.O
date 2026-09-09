"""Tasks API Router."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from packages.schemas.tasks import Task, TaskStatus
from apps.api.deps import Container, get_container

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: str, container: Container = Depends(get_container)):
    """Retrieve the current DAG graph and status of a task."""
    task = container.orchestrator.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str, container: Container = Depends(get_container)):
    """Cancel a running task."""
    task = container.orchestrator.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = TaskStatus.CANCELLED
    return {"status": "cancelled", "task_id": task_id}
