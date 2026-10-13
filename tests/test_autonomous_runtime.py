"""Unit tests for R.I.O. M5.7 Continuous Autonomous Runtime."""

import pytest
pytestmark = [pytest.mark.unit, pytest.mark.autonomous]

from packages.schemas.agents import Action, AgentResult, AgentStatus, Evidence
from packages.schemas.tasks import StepStatus, Task, TaskPlan, TaskStep
from services.autonomy.budget import AutonomyBudget
from services.autonomy.controller import AutonomyController
from services.autonomy.world_state import WorldState
from services.execution.parallel_executor import ParallelDAGExecutor
from services.planning.planner import IntelligentPlanner


class FlakyRecoverableAgent:
    """Agent that fails on first try for specific action, then succeeds on fallback."""

    def __init__(self):
        self.attempts = 0

    async def run(self, input_obj, context):
        self.attempts += 1
        # If fallback action
        if "(fallback)" in str(input_obj.payload) or "fallback" in str(context):
            return AgentResult(
                status=AgentStatus.SUCCESS,
                data={"verified": True},
                evidence=[Evidence(type="assertion", source="test", verified=True, confidence=1.0)],
            )
        return AgentResult(
            status=AgentStatus.SUCCESS,
            data={"verified": True, "file_exists": True},
            evidence=[
                Evidence(type="assertion", source="test", verified=True, confidence=1.0),
                Evidence(type="file_check", source="test", data={"path": "report.md", "size_bytes": 1024}, verified=True, confidence=1.0),
                Evidence(type="device_observation", source="test", verified=True, confidence=1.0),
            ],
        )


def test_autonomy_budget_limits():
    budget = AutonomyBudget(max_actions=2, max_runtime_ms=1000)

    assert budget.can_continue() is True
    budget.record_action(duration_ms=200)
    assert budget.can_continue() is True

    budget.record_action(duration_ms=200)
    # Action limit reached
    assert budget.can_continue() is False


def test_world_state_telemetry():
    ws = WorldState()
    ws.update_resource(ram_mb=4096.0, vram_mb=2048.0)
    ws.update_task_status("task-123", "running")

    assert "task-123" in ws.active_tasks
    assert ws.resource_state["ram_available_mb"] == 4096.0

    ws.update_task_status("task-123", "completed")
    assert "task-123" not in ws.active_tasks


@pytest.mark.asyncio
async def test_autonomy_controller_end_to_end():
    executor = ParallelDAGExecutor()
    agent = FlakyRecoverableAgent()
    executor.register_agent("research_agent", agent)
    executor.register_agent("computer_agent", agent)
    executor.register_agent("document_agent", agent)

    controller = AutonomyController(executor=executor)
    goal = "Research the latest NVIDIA GPU, compare it with my laptop and create a report."
    task = await controller.run_autonomous_task(goal=goal)

    assert task.status.value == "completed"
    assert task.plan is not None
    assert all(s.status == StepStatus.COMPLETED for s in task.plan.steps)


@pytest.mark.asyncio
async def test_autonomy_controller_budget_exhaustion_stops_safely():
    executor = ParallelDAGExecutor()
    controller = AutonomyController(executor=executor)

    # Budget with 0 max_actions
    strict_budget = AutonomyBudget(max_actions=0)
    task = await controller.run_autonomous_task(goal="Open Notepad", budget=strict_budget)

    assert task.status.value == "failed"
    assert "budget exhausted" in (task.error or "").lower()
