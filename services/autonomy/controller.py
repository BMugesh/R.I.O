"""Autonomous Execution Controller for R.I.O. (Milestone 5).

Coordinates the continuous autonomous loop:
Observe -> Interpret -> Plan -> Act -> Observe -> Verify -> Decide -> Complete / Recover
within explicit safety, budget, and device boundaries.
"""

import asyncio
from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, Optional

from packages.schemas.tasks import StepStatus, Task, TaskPlan, TaskStatus, TaskStep
from services.autonomy.budget import AutonomyBudget
from services.autonomy.world_state import WorldState
from services.execution.parallel_executor import ParallelDAGExecutor
from services.planning.planner import IntelligentPlanner
from services.recovery.classifier import FailureClassifier, FailureType
from services.recovery.replanner import Replanner
from services.recovery.retry_policy import RetryPolicy

logger = logging.getLogger("rio.autonomy.controller")


class AutonomyController:
    """Orchestrates bounded, evidence-driven autonomous execution."""

    def __init__(
        self,
        planner: Optional[IntelligentPlanner] = None,
        executor: Optional[ParallelDAGExecutor] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ):
        self.planner = planner or IntelligentPlanner()
        self.executor = executor or ParallelDAGExecutor()
        self.retry_policy = retry_policy or RetryPolicy(max_retries=2)
        self.world_state = WorldState()

    async def run_autonomous_task(
        self,
        goal: str,
        budget: Optional[AutonomyBudget] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Task:
        """Run an autonomous workflow from high-level goal to verified completion."""
        task_budget = budget or AutonomyBudget()
        start_time = time.time()

        # 1. Plan Phase
        plan = await self.planner.plan(goal=goal, context=context)
        task = Task(goal=goal, plan=plan, status=TaskStatus.RUNNING)
        self.world_state = WorldState.capture_current_snapshot(self.world_state.active_tasks)
        self.world_state.update_task_status(task.id, "running")

        # 2. Autonomous Execution Loop
        while task.status == TaskStatus.RUNNING:
            # Check budget
            elapsed_ms = int((time.time() - start_time) * 1000)
            task_budget.current_runtime_ms = elapsed_ms

            if not task_budget.can_continue():
                logger.warning(f"AutonomyController: Budget exhausted for task {task.id}.")
                task.status = TaskStatus.FAILED
                task.error = "Autonomy budget exhausted (action limit, time limit, or replan limit reached)."
                break

            # Execute graph via parallel executor
            task = await self.executor.execute_task(task, context=context)

            # Check if task encountered a recoverable failure
            if task.status == TaskStatus.FAILED and task.plan:
                failed_steps = [s for s in task.plan.steps if s.status == StepStatus.FAILED]
                if failed_steps and task_budget.current_replans < task_budget.max_replans:
                    f_step = failed_steps[0]
                    f_type = FailureClassifier.classify(f_step.error or "")

                    # If failure can be replanned / recovered
                    if f_type in (FailureType.TOOL, FailureType.RESOURCE, FailureType.NETWORK, FailureType.VERIFICATION):
                        logger.info(f"AutonomyController attempting replanning for failed step {f_step.name}")
                        task_budget.record_replan()
                        repaired_plan = Replanner.replan_failed_step(
                            task=task,
                            failed_step=f_step,
                            failure_reason=f_step.error or "Step failed",
                            context=context,
                        )
                        if repaired_plan:
                            task.plan = repaired_plan
                            task.status = TaskStatus.RUNNING
                            task.error = None
                            continue

            # If not replanning, break loop
            break

        self.world_state.update_task_status(task.id, task.status.value)
        return task
