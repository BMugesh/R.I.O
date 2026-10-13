"""Execution Optimizer for R.I.O. (Milestone 5).

Analyzes DAG dependency levels and groups steps into parallel execution waves/stages,
calculating critical paths and estimated wall-clock latencies.
"""

from typing import Dict, List, Set, Tuple
from packages.schemas.tasks import TaskStep
from services.planning.dependency_analyzer import DependencyAnalyzer
from services.planning.plan_models import PlanOptimizationSummary


class ExecutionOptimizer:
    """Optimizes execution ordering by computing dependency stages and critical paths."""

    @staticmethod
    def optimize(steps: List[TaskStep]) -> PlanOptimizationSummary:
        """Partition steps into ordered execution stages (waves) where all steps in a stage
        can safely run concurrently because all dependencies are in earlier stages.
        """
        if not steps:
            return PlanOptimizationSummary(stages=[], max_parallelism=0)

        step_map = {s.id: s for s in steps}
        adj, in_degree = DependencyAnalyzer.build_graph(steps)

        # Track when each step becomes ready
        step_levels: Dict[str, int] = {}

        # Compute level for each node
        # Level 0 = no dependencies
        # Level N = max(level of all dependencies) + 1
        # Using topological ordering ensures dependencies are computed before node
        ordered_steps = DependencyAnalyzer.topological_sort(steps)

        for step in ordered_steps:
            if not step.dependencies:
                step_levels[step.id] = 0
            else:
                max_dep_level = max(step_levels.get(d, 0) for d in step.dependencies)
                step_levels[step.id] = max_dep_level + 1

        # Group steps by level
        max_level = max(step_levels.values()) if step_levels else 0
        stages: List[List[str]] = [[] for _ in range(max_level + 1)]

        for sid, lvl in step_levels.items():
            stages[lvl].append(sid)

        max_parallelism = max(len(stage) for stage in stages) if stages else 1

        # Compute critical path and estimated duration
        total_duration = 0
        critical_path: List[str] = []
        for stage in stages:
            stage_steps = [step_map[sid] for sid in stage]
            # Duration of a stage is the max duration of its steps
            stage_duration = max(
                (s.estimated_duration_ms or 1000) for s in stage_steps
            ) if stage_steps else 0
            total_duration += stage_duration
            if stage:
                critical_path.append(stage[0])

        return PlanOptimizationSummary(
            stages=stages,
            max_parallelism=max_parallelism,
            critical_path=critical_path,
            estimated_total_duration_ms=total_duration,
        )
