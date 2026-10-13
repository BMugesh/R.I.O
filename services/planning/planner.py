"""Intelligent Task Planner for R.I.O. (Milestone 5).

Transforms user intent into verified, dependency-aware, resource-estimated,
and parallel-optimized DAG execution plans.
"""

import logging
from typing import Any, Dict, List, Optional
import uuid

from packages.schemas.agents import Action, AgentRiskLevel
from packages.schemas.tasks import TaskPlan, TaskStep, VerificationStrategy
from services.planning.dependency_analyzer import DependencyAnalyzer
from services.planning.execution_optimizer import ExecutionOptimizer
from services.planning.plan_models import TaskAnalysis
from services.planning.plan_validator import PlanValidator
from services.planning.task_analyzer import TaskAnalyzer
from services.planning.task_decomposer import TaskDecomposer

logger = logging.getLogger("rio.planning")


class IntelligentPlanner:
    """Core Intelligent Task Planner coordinating analysis, decomposition, validation, and optimization."""

    def __init__(self, dag_planner_fallback: Optional[Any] = None):
        self.analyzer = TaskAnalyzer()
        self.decomposer = TaskDecomposer()
        self.validator = PlanValidator()
        self.optimizer = ExecutionOptimizer()
        self.dag_planner_fallback = dag_planner_fallback

    async def plan(self, goal: str, context: Optional[Dict[str, Any]] = None) -> TaskPlan:
        """Create a validated, optimized DAG plan from a user goal."""
        # 1. Structural and resource analysis
        analysis = self.analyzer.analyze(goal=goal, context=context)

        steps: Optional[List[TaskStep]] = None

        # 2. Check for multi-target parallel decomposition
        parallel_steps = self.decomposer.decompose_parallel_research(goal=goal, analysis=analysis)
        if parallel_steps:
            steps = parallel_steps

        # 3. If no parallel decomposition matched, delegate to DAGPlanner template heuristics if available
        if not steps and self.dag_planner_fallback:
            fallback_plan = await self.dag_planner_fallback.create_plan(goal=goal, context=context)
            steps = fallback_plan.steps

        # 4. Fallback atomic step if still empty
        if not steps:
            s_id = str(uuid.uuid4())
            steps = [
                TaskStep(
                    id=s_id,
                    name="Execute Action",
                    description=goal,
                    agent_id="conversation_agent",
                    action=Action(action_type="process", parameters={"query": goal}),
                    dependencies=[],
                    parallelizable=False,
                    risk_level=AgentRiskLevel.LOW,
                    verification_strategy=VerificationStrategy(strategy_type="assertion", expected_state={"verified": True}),
                )
            ]

        # 5. Enrich steps with resource and verification metadata from analysis
        for step in steps:
            if step.verification_level is None:
                step.verification_level = analysis.verification_level
            if step.estimated_duration_ms is None:
                step.estimated_duration_ms = 1200 if step.parallelizable else 1800
            if step.estimated_memory_mb is None:
                step.estimated_memory_mb = 150
            if step.estimated_vram_mb is None:
                step.estimated_vram_mb = 600 if "gpu" in step.action.action_type or "vision" in step.agent_id else 0

        # 6. Optimize execution stages and critical path
        optimization = self.optimizer.optimize(steps)

        # 7. Construct TaskPlan
        plan = TaskPlan(
            id=str(uuid.uuid4()),
            goal=goal,
            steps=steps,
            estimated_duration_seconds=float(optimization.estimated_total_duration_ms) / 1000.0,
            analysis=analysis.model_dump(),
            execution_stages=optimization.stages,
            max_parallelism=optimization.max_parallelism,
        )

        # 8. Validate plan
        val_result = self.validator.validate(plan, context=context)
        if not val_result.is_valid:
            logger.error(f"Plan validation failed: {val_result.errors}")
            raise ValueError(f"Generated invalid task plan: {'; '.join(val_result.errors)}")

        return plan
