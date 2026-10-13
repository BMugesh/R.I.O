"""Asynchronous Task Graph Execution Engine for R.I.O.

Executes DAG task plans, coordinates agent dispatching, handles approval gates,
collects observations, verifies step outcomes, and manages error recovery.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Callable, Dict, List, Optional
from packages.schemas.agents import AgentResult, AgentStatus
from packages.schemas.events import EventType, RIOEvent
from packages.schemas.safety import ApprovalStatus
from packages.schemas.tasks import StepStatus, Task, TaskPlan, TaskStatus, TaskStep
from services.execution.parallel_executor import ParallelDAGExecutor
from services.safety.approval_engine import ApprovalEngine
from services.verification.engine import VerificationEngine

logger = logging.getLogger("rio.execution_engine")


class ExecutionEngine:
    """DAG Task Runner and Event Bus Coordinator."""

    def __init__(
        self,
        approval_engine: Optional[ApprovalEngine] = None,
        verification_engine: Optional[VerificationEngine] = None,
        event_callback: Optional[Callable[[RIOEvent], Any]] = None,
    ):
        self.approval_engine = approval_engine or ApprovalEngine()
        self.verification_engine = verification_engine or VerificationEngine()
        self.event_callback = event_callback
        self._agents: Dict[str, Any] = {}
        self.parallel_executor = ParallelDAGExecutor(
            approval_engine=self.approval_engine,
            verification_engine=self.verification_engine,
            event_callback=self.event_callback,
        )

    def register_agent(self, agent_id: str, agent_instance: Any) -> None:
        """Register an agent instance for dispatch."""
        self._agents[agent_id] = agent_instance
        self.parallel_executor.register_agent(agent_id, agent_instance)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel an active task."""
        return self.parallel_executor.cancel_task(task_id)

    async def emit_event(self, event_type: EventType, task_id: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> None:
        """Emit internal event to bus and listeners."""
        await self.parallel_executor.emit_event(event_type, task_id=task_id, payload=payload)

    async def execute_task(self, task: Task, context: Optional[Dict[str, Any]] = None) -> Task:
        """Execute a full task graph using parallel DAG engine."""
        return await self.parallel_executor.execute_task(task, context=context)

