"""Replanner & Partial Success Coordinator for R.I.O. (Milestone 5).

Replans invalidated subgraphs following non-recoverable step failures while
strictly preserving already-completed work and intermediate results.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Set
import uuid

from packages.schemas.agents import Action, AgentRiskLevel
from packages.schemas.tasks import StepStatus, Task, TaskPlan, TaskStep, VerificationStrategy
from services.planning.plan_validator import PlanValidator
from services.recovery.fallback import FallbackManager

logger = logging.getLogger("rio.recovery.replanner")


class Replanner:
    """Dynamically repairs failed task plans by replacing failed nodes and rewiring dependencies."""

    @classmethod
    def replan_failed_step(
        cls,
        task: Task,
        failed_step: TaskStep,
        failure_reason: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[TaskPlan]:
        """Generate a repaired plan replacing the failed step with an alternative or fallback strategy."""
        if not task.plan:
            return None

        old_steps = task.plan.steps
        completed_step_ids = {s.id for s in old_steps if s.status == StepStatus.COMPLETED}

        # Check if an alternative tool or action exists
        fallback_action = FallbackManager.get_tool_fallback(failed_step.action.action_type)
        if fallback_action:
            alt_action_type = fallback_action
        elif not failed_step.action.action_type.endswith("_fallback"):
            alt_action_type = f"{failed_step.action.action_type}_fallback"
        else:
            alt_action_type = failed_step.action.action_type

        repl_params = dict(failed_step.action.parameters)
        if "action" in repl_params:
            repl_params["action"] = alt_action_type
        if "action_type" in repl_params:
            repl_params["action_type"] = alt_action_type

        alt_agent_id = failed_step.agent_id
        if alt_action_type in ("http.get", "search_web", "fetch_url"):
            alt_agent_id = "research_agent"

        # Create replacement step
        replacement_id = str(uuid.uuid4())
        replacement_step = TaskStep(
            id=replacement_id,
            name=f"{failed_step.name} (Fallback)",
            description=f"Fallback recovery execution for {failed_step.name} after: {failure_reason}",
            agent_id=alt_agent_id,
            action=Action(action_type=alt_action_type, parameters=repl_params),
            dependencies=[dep for dep in failed_step.dependencies if dep in completed_step_ids],
            parallelizable=False,
            risk_level=failed_step.risk_level,
            verification_strategy=failed_step.verification_strategy or VerificationStrategy(strategy_type="assertion", expected_state={"verified": True}),
        )

        new_steps: List[TaskStep] = []
        for s in old_steps:
            if s.id == failed_step.id:
                # Mark original as skipped/recovered and insert replacement
                s.status = StepStatus.SKIPPED
                s.error = f"Recovered by {replacement_id}"
                new_steps.append(s)
                new_steps.append(replacement_step)
            else:
                # Rewire any downstream step that depended on failed_step to depend on replacement_step
                if failed_step.id in s.dependencies:
                    updated_deps = [d if d != failed_step.id else replacement_id for d in s.dependencies]
                    s.dependencies = updated_deps
                new_steps.append(s)

        new_plan = TaskPlan(
            id=str(uuid.uuid4()),
            goal=task.plan.goal,
            steps=new_steps,
            estimated_duration_seconds=task.plan.estimated_duration_seconds + 2.0,
            analysis=task.plan.analysis,
        )

        # Validate new plan
        val = PlanValidator.validate(new_plan, context=context)
        if not val.is_valid:
            logger.error(f"Replanned graph failed validation: {val.errors}")
            return None

        logger.info(f"Successfully replanned task {task.id}: substituted step {failed_step.id} with {replacement_id}")
        return new_plan

    @staticmethod
    def evaluate_partial_success(task: Task) -> Dict[str, Any]:
        """Assess partial completion when some steps completed and others failed."""
        if not task.plan:
            return {"status": "failed", "completed_count": 0, "total_count": 0}

        steps = task.plan.steps
        completed = [s for s in steps if s.status == StepStatus.COMPLETED]
        failed = [s for s in steps if s.status == StepStatus.FAILED]

        is_partial = len(completed) > 0 and len(failed) > 0
        return {
            "status": "partial" if is_partial else ("completed" if len(completed) == len(steps) else "failed"),
            "completed_count": len(completed),
            "failed_count": len(failed),
            "total_count": len(steps),
            "completed_step_names": [s.name for s in completed],
            "failed_step_names": [s.name for s in failed],
        }
