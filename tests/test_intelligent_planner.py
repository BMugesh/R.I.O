"""Unit tests for R.I.O. M5.1 Intelligent Task Planning."""

import pytest
pytestmark = [pytest.mark.unit, pytest.mark.planning]

from packages.schemas.agents import Action, AgentRiskLevel
from packages.schemas.tasks import TaskPlan, TaskStep, VerificationStrategy
from services.planning.dependency_analyzer import DependencyAnalyzer, DependencyCycleError
from services.planning.execution_optimizer import ExecutionOptimizer
from services.planning.plan_validator import PlanValidator
from services.planning.planner import IntelligentPlanner
from services.planning.task_analyzer import TaskAnalyzer
from services.planning.task_decomposer import TaskDecomposer


def test_task_analyzer_low_risk_simple():
    analyzer = TaskAnalyzer()
    analysis = analyzer.analyze("Open Notepad")

    assert analysis.complexity == "low"
    assert analysis.risk_level == "low"
    assert analysis.reversible is True
    assert analysis.requires_approval is False
    assert analysis.requires_gpu is False
    assert analysis.verification_level == "basic"


def test_task_analyzer_destructive_critical():
    analyzer = TaskAnalyzer()
    analysis = analyzer.analyze("Delete all temporary log files in /var/log")

    assert analysis.risk_level == "critical"
    assert analysis.reversible is False
    assert analysis.requires_approval is True
    assert analysis.verification_level == "critical"


def test_task_analyzer_gpu_and_network():
    analyzer = TaskAnalyzer()
    analysis = analyzer.analyze("Research latest vision models on the web and transcribe audio")

    assert "gpu_compute" in analysis.required_capabilities
    assert "network_access" in analysis.required_capabilities
    assert analysis.requires_gpu is True
    assert analysis.requires_network is True
    assert analysis.estimated_vram_mb >= 1000


def test_dependency_analyzer_topological_sort():
    s1 = TaskStep(id="s1", name="Step 1", agent_id="research_agent", action=Action(action_type="search"), dependencies=[])
    s2 = TaskStep(id="s2", name="Step 2", agent_id="research_agent", action=Action(action_type="search"), dependencies=["s1"])
    s3 = TaskStep(id="s3", name="Step 3", agent_id="document_agent", action=Action(action_type="write"), dependencies=["s2"])

    ordered = DependencyAnalyzer.topological_sort([s3, s1, s2])
    ordered_ids = [s.id for s in ordered]
    assert ordered_ids == ["s1", "s2", "s3"]


def test_dependency_analyzer_cycle_detection():
    s1 = TaskStep(id="s1", name="Step 1", agent_id="research_agent", action=Action(action_type="search"), dependencies=["s2"])
    s2 = TaskStep(id="s2", name="Step 2", agent_id="research_agent", action=Action(action_type="search"), dependencies=["s1"])

    cycle = DependencyAnalyzer.detect_cycles([s1, s2])
    assert cycle is not None
    assert "s1" in cycle and "s2" in cycle

    with pytest.raises(DependencyCycleError):
        DependencyAnalyzer.topological_sort([s1, s2])


def test_plan_validator_catches_invalid_dependency():
    s1 = TaskStep(id="s1", name="Step 1", agent_id="research_agent", action=Action(action_type="search"), dependencies=["s99"])
    plan = TaskPlan(goal="Test invalid", steps=[s1])

    val = PlanValidator.validate(plan)
    assert val.is_valid is False
    assert any("non-existent step id: s99" in err for err in val.errors)


def test_plan_validator_catches_self_dependency():
    s1 = TaskStep(id="s1", name="Step 1", agent_id="research_agent", action=Action(action_type="search"), dependencies=["s1"])
    plan = TaskPlan(goal="Test self dep", steps=[s1])

    val = PlanValidator.validate(plan)
    assert val.is_valid is False
    assert any("depends on itself" in err for err in val.errors)


def test_task_decomposer_parallel_research():
    analyzer = TaskAnalyzer()
    goal = "Research RTX 4090, Apple M3, and Snapdragon X Elite and create a report"
    analysis = analyzer.analyze(goal)

    decomposer = TaskDecomposer()
    steps = decomposer.decompose_parallel_research(goal, analysis)

    assert steps is not None
    assert len(steps) >= 4  # 3 research steps + 1 comparison/report step
    parallel_steps = [s for s in steps if s.parallelizable]
    assert len(parallel_steps) >= 3


def test_execution_optimizer_stages():
    s1 = TaskStep(id="s1", name="Parallel 1", agent_id="research_agent", action=Action(action_type="search"), dependencies=[])
    s2 = TaskStep(id="s2", name="Parallel 2", agent_id="research_agent", action=Action(action_type="search"), dependencies=[])
    s3 = TaskStep(id="s3", name="Merge", agent_id="research_agent", action=Action(action_type="compare"), dependencies=["s1", "s2"])

    summary = ExecutionOptimizer.optimize([s1, s2, s3])
    assert len(summary.stages) == 2
    assert set(summary.stages[0]) == {"s1", "s2"}
    assert summary.stages[1] == ["s3"]
    assert summary.max_parallelism == 2


@pytest.mark.asyncio
async def test_intelligent_planner_e2e():
    planner = IntelligentPlanner()
    goal = "Research the latest NVIDIA GPU, compare it with my laptop and create a report."
    plan = await planner.plan(goal)

    assert plan.goal == goal
    assert len(plan.steps) == 4
    assert plan.max_parallelism == 2
    assert len(plan.execution_stages) == 3
    assert plan.analysis is not None
    assert plan.analysis["requires_network"] is True
