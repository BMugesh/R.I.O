"""Plan Validator for R.I.O. (Milestone 5).

Strict pre-execution validation ensuring DAG safety, dependency integrity,
action executability, verification adequacy, and human approval compliance.
"""

from typing import Any, Dict, List, Optional, Set
from packages.schemas.agents import AgentRiskLevel
from packages.schemas.tasks import TaskPlan, TaskStep
from services.planning.dependency_analyzer import DependencyAnalyzer
from services.planning.plan_models import PlanValidationResult


class PlanValidator:
    """Validates that a generated TaskPlan is safe and structurally sound."""

    KNOWN_AGENTS = {
        "conversation_agent",
        "planner_agent",
        "research_agent",
        "coding_agent",
        "browser_agent",
        "computer_agent",
        "vision_agent",
        "document_agent",
        "filesystem_agent",
        "github_agent",
        "device_agent",
        "verification_agent",
        "memory_agent",
        "quantum_agent",
        "local_system_agent",
        "system_agent",
    }

    @classmethod
    def validate(cls, plan: TaskPlan, context: Optional[Dict[str, Any]] = None) -> PlanValidationResult:
        """Perform comprehensive validation on a TaskPlan.

        Invalid plans must never enter execution.
        """
        errors: List[str] = []
        warnings: List[str] = []

        if not plan.steps:
            return PlanValidationResult(is_valid=True, warnings=["Plan contains no steps."])

        step_ids: Set[str] = set()
        for step in plan.steps:
            if not step.id:
                errors.append(f"Step '{step.name}' has no valid id.")
            elif step.id in step_ids:
                errors.append(f"Duplicate step id detected: {step.id}")
            step_ids.add(step.id)

        # 1. Dependency Validation: check existence and self-dependency
        for step in plan.steps:
            for dep in step.dependencies:
                if dep == step.id:
                    errors.append(f"Step '{step.name}' ({step.id}) depends on itself.")
                elif dep not in step_ids:
                    errors.append(f"Step '{step.name}' depends on non-existent step id: {dep}")

        # 2. Cycle Detection
        cycle = DependencyAnalyzer.detect_cycles(plan.steps)
        if cycle:
            errors.append(f"Cyclic dependency detected in task plan: {' -> '.join(cycle)}")

        # 3. Executability & Agent Check
        for step in plan.steps:
            if not step.action or not step.action.action_type:
                errors.append(f"Step '{step.name}' ({step.id}) has no executable action_type.")

            if step.agent_id not in cls.KNOWN_AGENTS:
                warnings.append(f"Step '{step.name}' specifies unverified agent '{step.agent_id}'. Fallback execution will be used.")

            # 4. Human Approval Gates
            if step.risk_level in (AgentRiskLevel.HIGH, AgentRiskLevel.CRITICAL):
                if not step.requires_approval:
                    warnings.append(f"High/Critical risk step '{step.name}' automatically assigned approval requirement.")
                    step.requires_approval = True

            # 5. Verification Strategy Check
            if not step.verification_strategy:
                warnings.append(f"Step '{step.name}' lacks an explicit verification strategy; default assertion will be applied.")

        is_valid = len(errors) == 0
        return PlanValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)
