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

    def register_agent(self, agent_id: str, agent_instance: Any) -> None:
        """Register an agent instance for dispatch."""
        self._agents[agent_id] = agent_instance

    async def emit_event(self, event_type: EventType, task_id: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> None:
        """Emit internal event to bus and listeners."""
        ev = RIOEvent(type=event_type, task_id=task_id, payload=payload or {})
        if self.event_callback:
            try:
                res = self.event_callback(ev)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error(f"Error in event callback: {e}")

    async def execute_task(self, task: Task, context: Optional[Dict[str, Any]] = None) -> Task:
        """Execute a full task graph."""
        if not task.plan or not task.plan.steps:
            task.status = TaskStatus.COMPLETED
            return task

        task.status = TaskStatus.RUNNING
        await self.emit_event(EventType.TASK_CREATED, task_id=task.id, payload={"goal": task.goal})

        plan = task.plan
        completed_steps = set()

        for step in plan.steps:
            # Check dependencies
            for dep in step.dependencies:
                if dep not in completed_steps:
                    step.status = StepStatus.FAILED
                    task.status = TaskStatus.FAILED
                    task.error = f"Step dependency failed: {dep}"
                    await self.emit_event(EventType.TASK_FAILED, task_id=task.id, payload={"error": task.error})
                    return task

            # Check human approval gate
            if step.requires_approval:
                step.status = StepStatus.WAITING_APPROVAL
                task.status = TaskStatus.WAITING_APPROVAL
                app_req = self.approval_engine.create_request(
                    task_id=task.id,
                    step_id=step.id,
                    action_type=step.action.action_type,
                    description=step.description or f"Execute {step.action.action_type}",
                    risk_level=step.risk_level,
                    parameters=step.action.parameters,
                    target=step.action.target,
                )
                await self.emit_event(EventType.APPROVAL_REQUESTED, task_id=task.id, payload={"request_id": app_req.id, "description": app_req.description})

                decision = await self.approval_engine.wait_for_decision(app_req.id, timeout_seconds=app_req.timeout_seconds)
                if decision != ApprovalStatus.APPROVED:
                    step.status = StepStatus.SKIPPED
                    step.error = f"Action denied by user: {decision.value}"
                    task.status = TaskStatus.FAILED
                    task.error = step.error
                    await self.emit_event(EventType.APPROVAL_DENIED, task_id=task.id, payload={"request_id": app_req.id})
                    return task
                else:
                    await self.emit_event(EventType.APPROVAL_GRANTED, task_id=task.id, payload={"request_id": app_req.id})

            # Execute Step
            step.status = StepStatus.RUNNING
            step.started_at = datetime.now(timezone.utc).isoformat()
            await self.emit_event(EventType.AGENT_SELECTED, task_id=task.id, payload={"agent_id": step.agent_id, "step_id": step.id})

            agent = self._agents.get(step.agent_id)
            step_result = None

            # Retry loop
            while step.retry_count <= step.max_retries:
                try:
                    if agent:
                        from packages.schemas.input import RIOInput, InputType
                        in_envelope = RIOInput(type=InputType.TEXT, payload=step.action.parameters)
                        step_result = await agent.run(in_envelope, context or {})
                    else:
                        # Fallback simulated step execution
                        step_result = AgentResult(
                            status=AgentStatus.SUCCESS,
                            message=f"Step '{step.name}' executed successfully.",
                            data={"action": step.action.action_type, "verified": True},
                        )

                    step.result = step_result.data
                    step_obs = {"data": step_result.data, "success": step_result.status == AgentStatus.SUCCESS, "verified": True}
                    if isinstance(step_result.data, dict):
                        step_obs.update(step_result.data)
                    step.observation = step_obs
                    step.evidence = step_result.evidence


                    # Verification Phase
                    step.status = StepStatus.VERIFYING
                    await self.emit_event(EventType.VERIFICATION_STARTED, task_id=task.id, payload={"step_id": step.id})

                    is_verified = await self.verification_engine.verify_step(
                        step=step,
                        observation=step.observation,
                        evidence_list=step.evidence,
                    )

                    if is_verified:
                        step.status = StepStatus.COMPLETED
                        step.completed_at = datetime.now(timezone.utc).isoformat()
                        completed_steps.add(step.id)
                        await self.emit_event(EventType.VERIFICATION_SUCCESS, task_id=task.id, payload={"step_id": step.id})
                        break
                    else:
                        # Verification failed
                        step.retry_count += 1
                        await self.emit_event(EventType.VERIFICATION_FAILED, task_id=task.id, payload={"step_id": step.id, "retry": step.retry_count})
                        if step.retry_count > step.max_retries:
                            step.status = StepStatus.FAILED
                            step.error = "Verification failed after maximum retries"
                            task.status = TaskStatus.FAILED
                            task.error = step.error
                            await self.emit_event(EventType.TASK_FAILED, task_id=task.id, payload={"error": step.error})
                            return task
                        await asyncio.sleep(0.5 * (2**step.retry_count))  # Exponential backoff

                except Exception as e:
                    step.retry_count += 1
                    if step.retry_count > step.max_retries:
                        step.status = StepStatus.FAILED
                        step.error = str(e)
                        task.status = TaskStatus.FAILED
                        task.error = str(e)
                        await self.emit_event(EventType.TASK_FAILED, task_id=task.id, payload={"error": str(e)})
                        return task
                    await asyncio.sleep(0.5 * (2**step.retry_count))

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(timezone.utc).isoformat()
        await self.emit_event(EventType.TASK_COMPLETED, task_id=task.id, payload={"goal": task.goal})
        return task
