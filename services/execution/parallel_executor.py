"""Parallel DAG Execution Engine for R.I.O. (Milestone 5).

Executes DAG task plans with true concurrency for independent steps,
integrating resource-aware concurrency limits, human approval gates,
and cooperative task cancellation.
"""

import asyncio
from datetime import datetime, timezone
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set
import uuid

from packages.schemas.agents import Action, AgentResult, AgentStatus
from packages.schemas.events import EventType, RIOEvent
from packages.schemas.input import InputType, RIOInput
from packages.schemas.safety import ApprovalStatus
from packages.schemas.tasks import AutonomyBudget, StepStatus, Task, TaskPlan, TaskStatus, TaskStep
from services.execution.execution_context import ExecutionContext
from services.execution.resource_scheduler import ResourceScheduler
from services.recovery.classifier import FailureClassifier, FailureType
from services.recovery.replanner import Replanner
from services.recovery.retry_policy import RetryPolicy
from services.safety.approval_engine import ApprovalEngine
from services.verification.engine import VerificationEngine

logger = logging.getLogger("rio.execution.parallel_executor")


class ParallelDAGExecutor:
    """Executes DAG plans concurrently while strictly respecting dependencies and resource budgets."""

    def __init__(
        self,
        approval_engine: Optional[ApprovalEngine] = None,
        verification_engine: Optional[VerificationEngine] = None,
        resource_scheduler: Optional[ResourceScheduler] = None,
        retry_policy: Optional[RetryPolicy] = None,
        max_replans: int = 2,
        event_callback: Optional[Callable[[RIOEvent], Any]] = None,
    ):
        self.approval_engine = approval_engine or ApprovalEngine()
        self.verification_engine = verification_engine or VerificationEngine()
        self.resource_scheduler = resource_scheduler or ResourceScheduler()
        self.retry_policy = retry_policy or RetryPolicy(max_retries=2, initial_delay=0.1)
        self.max_replans = max_replans
        self.event_callback = event_callback
        self._agents: Dict[str, Any] = {}
        self._cancelled_tasks: Set[str] = set()
        self._active_async_tasks: Dict[str, List[asyncio.Task]] = {}

    def register_agent(self, agent_id: str, agent_instance: Any) -> None:
        """Register an agent instance for step dispatch."""
        self._agents[agent_id] = agent_instance

    def _resolve_agent(self, agent_id: str) -> Optional[Any]:
        """Resolve agent from registry or lazily instantiate standard built-in agent."""
        if agent_id in self._agents:
            return self._agents[agent_id]

        try:
            if agent_id in ("conversation_agent", "conversation"):
                from agents.conversation.agent import ConversationAgent
                agent = ConversationAgent()
            elif agent_id in ("planner_agent", "planner"):
                from agents.planner.agent import PlannerAgent
                agent = PlannerAgent()
            elif agent_id in ("research_agent", "research"):
                from agents.research.agent import ResearchAgent
                agent = ResearchAgent()
            elif agent_id in ("coding_agent", "coding"):
                from agents.coding.agent import CodingAgent
                agent = CodingAgent()
            elif agent_id in ("browser_agent", "browser"):
                from agents.browser.agent import BrowserAgent
                agent = BrowserAgent()
            elif agent_id in ("computer_agent", "computer"):
                from agents.computer.agent import ComputerAgent
                agent = ComputerAgent()
            elif agent_id in ("vision_agent", "vision"):
                from agents.vision.agent import VisionAgent
                agent = VisionAgent()
            elif agent_id in ("document_agent", "document"):
                from agents.document.agent import DocumentAgent
                agent = DocumentAgent()
            elif agent_id in ("filesystem_agent", "filesystem"):
                from agents.filesystem.agent import FileSystemAgent
                agent = FileSystemAgent()
            elif agent_id in ("github_agent", "github"):
                from agents.github.agent import GitHubAgent
                agent = GitHubAgent()
            elif agent_id in ("device_agent", "device"):
                from agents.device.agent import DeviceAgent
                agent = DeviceAgent()
            elif agent_id in ("verification_agent", "verification"):
                from agents.verification.agent import VerificationAgent
                agent = VerificationAgent()
            elif agent_id in ("memory_agent", "memory"):
                from agents.memory.agent import MemoryAgent
                agent = MemoryAgent()
            elif agent_id in ("quantum_agent", "quantum"):
                from agents.quantum.agent import QuantumAgent
                agent = QuantumAgent()
            elif agent_id in ("local_system_agent", "system_agent", "system"):
                from agents.system.agent import LocalSystemAgent
                agent = LocalSystemAgent()
            else:
                return None

            self._agents[agent_id] = agent
            return agent
        except Exception as e:
            logger.warning(f"Could not lazily instantiate agent {agent_id}: {e}")
            return None

    def cancel_task(self, task_id: str) -> bool:
        """Cooperatively cancel an active task execution."""
        self._cancelled_tasks.add(task_id)
        tasks = self._active_async_tasks.get(task_id, [])
        for t in tasks:
            if not t.done():
                t.cancel()
        logger.info(f"Task {task_id} marked for cancellation ({len(tasks)} active coroutines cancelled).")
        return True

    async def emit_event(self, event_type: EventType, task_id: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> None:
        """Emit event to bus and registered callback."""
        ev = RIOEvent(type=event_type, task_id=task_id, payload=payload or {})
        if self.event_callback:
            try:
                res = self.event_callback(ev)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error(f"Error in event callback: {e}")

    async def execute_task(self, task: Task, context: Optional[Dict[str, Any]] = None) -> Task:
        """Execute a full task graph using wave/parallel dependency-aware dispatch."""
        if not task.plan or not task.plan.steps:
            task.status = TaskStatus.COMPLETED
            return task

        task.status = TaskStatus.RUNNING
        await self.emit_event(EventType.TASK_CREATED, task_id=task.id, payload={"goal": task.goal})

        budget = task.budget or AutonomyBudget()
        start_time = time.time()
        effective_max_replans = min(self.max_replans, budget.max_replans)
        total_steps_executed = 0

        completed_steps: Set[str] = set()
        failed_steps: Set[str] = set()
        step_map: Dict[str, TaskStep] = {s.id: s for s in task.plan.steps}
        self._active_async_tasks[task.id] = []

        # Continue until all steps are either completed or a fatal failure/cancellation occurs
        while len(completed_steps) + len(failed_steps) < len(task.plan.steps):
            if task.id in self._cancelled_tasks:
                task.status = TaskStatus.CANCELLED
                task.error = "Task execution was cancelled by user."
                await self.emit_event(EventType.TASK_FAILED, task_id=task.id, payload={"error": task.error})
                return task

            elapsed = time.time() - start_time
            if elapsed > budget.max_runtime_seconds:
                task.status = TaskStatus.FAILED
                task.error = f"Autonomy budget exceeded: runtime {elapsed:.2f}s exceeded limit of {budget.max_runtime_seconds:.2f}s."
                await self.emit_event(EventType.TASK_FAILED, task_id=task.id, payload={"error": task.error})
                return task

            if total_steps_executed >= budget.max_total_steps:
                task.status = TaskStatus.FAILED
                task.error = f"Autonomy budget exceeded: executed {total_steps_executed} steps, reaching limit of {budget.max_total_steps}."
                await self.emit_event(EventType.TASK_FAILED, task_id=task.id, payload={"error": task.error})
                return task

            # Find ready steps (dependencies satisfied and status PENDING)
            ready_steps = [
                s for s in task.plan.steps
                if s.status == StepStatus.PENDING
                and all(dep in completed_steps for dep in s.dependencies)
            ]

            if not ready_steps:
                # If no steps are ready and there are still unfinished steps, dependency cycle or failure deadlock
                unfinished = [s for s in task.plan.steps if s.id not in completed_steps and s.id not in failed_steps]
                if unfinished:
                    task.status = TaskStatus.FAILED
                    task.error = f"Unresolved dependencies for steps: {[s.name for s in unfinished]}"
                    await self.emit_event(EventType.TASK_FAILED, task_id=task.id, payload={"error": task.error})
                    return task
                break

            # If ready_steps has parallelizable steps, run them concurrently up to resource limits
            # Otherwise run step sequentially
            parallelizable_batch = [s for s in ready_steps if s.parallelizable]
            if len(parallelizable_batch) > 1:
                batch_to_run = parallelizable_batch
            else:
                batch_to_run = ready_steps[:1]

            # Execute batch within remaining time budget
            remaining_time = max(0.01, budget.max_runtime_seconds - (time.time() - start_time))
            coros = [self._execute_single_step(step, task, context, budget) for step in batch_to_run]
            batch_tasks = [asyncio.create_task(c) for c in coros]
            self._active_async_tasks[task.id].extend(batch_tasks)

            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*batch_tasks, return_exceptions=True),
                    timeout=remaining_time,
                )
            except asyncio.TimeoutError:
                for t in batch_tasks:
                    if not t.done():
                        t.cancel()
                task.status = TaskStatus.FAILED
                task.error = f"Autonomy budget exceeded: runtime exceeded limit of {budget.max_runtime_seconds:.2f}s."
                await self.emit_event(EventType.TASK_FAILED, task_id=task.id, payload={"error": task.error})
                return task

            total_steps_executed += len(batch_to_run)

            step_replanned = False
            for step, res in zip(batch_to_run, results):
                if isinstance(res, Exception):
                    step.status = StepStatus.FAILED
                    step.error = str(res)

                if step.status == StepStatus.COMPLETED:
                    completed_steps.add(step.id)
                elif step.status in (StepStatus.FAILED, StepStatus.SKIPPED):
                    failed_steps.add(step.id)
                    if step.action.action_type == "error_diagnostic":
                        task.status = TaskStatus.FAILED
                        task.error = step.error or "Capability check failed"
                        await self.emit_event(EventType.TASK_FAILED, task_id=task.id, payload={"error": task.error})
                        return task

                    # Dynamic Replanning: check if replan budget allows repairing this failure
                    replan_count = getattr(task, "_replan_count", 0)
                    if replan_count < effective_max_replans:
                        new_plan = Replanner.replan_failed_step(
                            task=task,
                            failed_step=step,
                            failure_reason=step.error or "Step execution failed",
                            context=context,
                        )
                        if new_plan:
                            task._replan_count = replan_count + 1
                            task.plan = new_plan
                            completed_steps = {s.id for s in new_plan.steps if s.status == StepStatus.COMPLETED}
                            failed_steps = {s.id for s in new_plan.steps if s.status == StepStatus.SKIPPED}
                            step_map = {s.id: s for s in new_plan.steps}
                            await self.emit_event(
                                EventType.TASK_CREATED,
                                task_id=task.id,
                                payload={"replan_attempt": task._replan_count, "repaired_plan_id": new_plan.id, "reason": step.error},
                            )
                            logger.info(f"Task {task.id} dynamically replanned after step '{step.name}' failed (replan {task._replan_count}/{effective_max_replans}).")
                            step_replanned = True
                            break

                    # Replan not possible or budget exhausted
                    partial_eval = Replanner.evaluate_partial_success(task)
                    task.status = TaskStatus.FAILED
                    task.error = step.error or "Step failed"
                    if partial_eval.get("completed_count", 0) > 0:
                        if not hasattr(task, "metadata") or task.metadata is None:
                            task.metadata = {}
                        task.metadata["partial_success"] = partial_eval
                    await self.emit_event(EventType.TASK_FAILED, task_id=task.id, payload={"error": task.error, "partial_success": partial_eval})
                    return task

            if step_replanned:
                continue

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(timezone.utc).isoformat()
        await self.emit_event(EventType.TASK_COMPLETED, task_id=task.id, payload={"goal": task.goal})
        return task

    async def _execute_single_step(self, step: TaskStep, task: Task, context: Optional[Dict[str, Any]], budget: Optional[AutonomyBudget] = None) -> None:
        """Execute and verify a single step within acquired resource slots."""
        # 1. Human Approval Gate
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
                await self.emit_event(EventType.APPROVAL_DENIED, task_id=task.id, payload={"request_id": app_req.id})
                return
            else:
                await self.emit_event(EventType.APPROVAL_GRANTED, task_id=task.id, payload={"request_id": app_req.id})

        # 2. Acquire Resource Slots
        async with self.resource_scheduler.acquire_slot(step):
            step.status = StepStatus.RUNNING
            step.started_at = datetime.now(timezone.utc).isoformat()
            await self.emit_event(EventType.AGENT_SELECTED, task_id=task.id, payload={"agent_id": step.agent_id, "step_id": step.id})

            if step.action.action_type == "error_diagnostic":
                err_msg = step.action.parameters.get("error") or step.description
                step.status = StepStatus.FAILED
                step.error = err_msg
                return

            agent = self._resolve_agent(step.agent_id)
            effective_max_retries = min(self.retry_policy.max_retries, budget.max_retries_per_step) if budget else self.retry_policy.max_retries

            while step.retry_count <= effective_max_retries:
                if task.id in self._cancelled_tasks:
                    step.status = StepStatus.SKIPPED
                    step.error = "Cancelled"
                    return

                try:
                    if agent:
                        step_payload = dict(step.action.parameters) if isinstance(step.action.parameters, dict) else {}
                        if "action_type" not in step_payload:
                            step_payload["action_type"] = step.action.action_type
                        if "action" not in step_payload:
                            step_payload["action"] = step.action.action_type
                        in_envelope = RIOInput(type=InputType.TEXT, payload=step_payload)
                        step_result = await agent.run(in_envelope, context or {})
                    else:
                        step_result = AgentResult(
                            status=AgentStatus.FAILED,
                            message=f"No agent registered with ID '{step.agent_id}' to execute step '{step.name}'.",
                            data={"action": step.action.action_type, "verified": False},
                        )

                    step.result = step_result.data
                    is_verified_from_data = bool(step_result.data.get("verified", False)) if isinstance(step_result.data, dict) else False
                    step_obs = {
                        "data": step_result.data,
                        "success": step_result.status == AgentStatus.SUCCESS,
                        "verified": is_verified_from_data and (step_result.status == AgentStatus.SUCCESS),
                    }
                    if isinstance(step_result.data, dict):
                        step_obs.update(step_result.data)
                    step.observation = step_obs
                    step.evidence = step_result.evidence

                    # If agent explicitly failed
                    if step_result.status == AgentStatus.FAILED:
                        fail_type = FailureClassifier.classify(step_result.message)
                        if self.retry_policy.should_retry(fail_type, step.retry_count, max_retries=effective_max_retries):
                            delay = self.retry_policy.compute_delay(step.retry_count)
                            step.retry_count += 1
                            await self.emit_event(EventType.VERIFICATION_FAILED, task_id=task.id, payload={"step_id": step.id, "retry": step.retry_count, "error": step_result.message})
                            await asyncio.sleep(delay)
                            continue
                        else:
                            step.status = StepStatus.FAILED
                            step.error = step_result.message or "Agent execution failed"
                            return

                    # 3. Verification Phase
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
                        if isinstance(context, dict):
                            context["last_observation"] = step_obs
                        await self.emit_event(EventType.VERIFICATION_SUCCESS, task_id=task.id, payload={"step_id": step.id})
                        return
                    else:
                        fail_type = FailureType.VERIFICATION
                        if self.retry_policy.should_retry(fail_type, step.retry_count, max_retries=effective_max_retries):
                            delay = self.retry_policy.compute_delay(step.retry_count)
                            step.retry_count += 1
                            await self.emit_event(EventType.VERIFICATION_FAILED, task_id=task.id, payload={"step_id": step.id, "retry": step.retry_count})
                            await asyncio.sleep(delay)
                            continue
                        else:
                            step.status = StepStatus.FAILED
                            step.error = f"Verification failed for step '{step.name}' after {step.retry_count} retries"
                            return

                except Exception as e:
                    fail_type = FailureClassifier.classify(str(e))
                    if self.retry_policy.should_retry(fail_type, step.retry_count, max_retries=effective_max_retries):
                        delay = self.retry_policy.compute_delay(step.retry_count)
                        step.retry_count += 1
                        await asyncio.sleep(delay)
                        continue
                    else:
                        step.status = StepStatus.FAILED
                        step.error = str(e)
                        return
