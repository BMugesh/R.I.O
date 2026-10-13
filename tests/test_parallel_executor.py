"""Unit tests for R.I.O. M5.2 Parallel DAG Execution & Resource-Aware Concurrency."""

import asyncio
import time
import pytest
pytestmark = [pytest.mark.unit, pytest.mark.execution]

from packages.schemas.agents import Action, AgentResult, AgentRiskLevel, AgentStatus, Evidence
from packages.schemas.safety import ApprovalDecision, ApprovalStatus
from packages.schemas.tasks import StepStatus, Task, TaskPlan, TaskStep, VerificationStrategy
from services.execution.parallel_executor import ParallelDAGExecutor
from services.execution.queue import ExecutionQueue, TaskPriority
from services.execution.resource_scheduler import ResourceScheduler
from services.safety.approval_engine import ApprovalEngine
from services.verification.engine import VerificationEngine


class SlowMockAgent:
    """Mock agent simulating a slow concurrent operation."""

    def __init__(self, delay: float = 0.2):
        self.delay = delay
        self.call_count = 0
        self.active_concurrent = 0
        self.max_concurrent = 0

    async def run(self, input_obj, context):
        self.call_count += 1
        self.active_concurrent += 1
        if self.active_concurrent > self.max_concurrent:
            self.max_concurrent = self.active_concurrent
        try:
            await asyncio.sleep(self.delay)
            return AgentResult(
                status=AgentStatus.SUCCESS,
                data={"verified": True, "count": self.call_count},
                evidence=[Evidence(type="assertion", source="mock", verified=True, confidence=1.0)],
            )
        finally:
            self.active_concurrent -= 1


@pytest.mark.asyncio
async def test_parallel_execution_speedup():
    """Verify that independent parallelizable steps execute concurrently."""
    executor = ParallelDAGExecutor()
    agent = SlowMockAgent(delay=0.2)
    executor.register_agent("mock_agent", agent)

    # Diamond DAG: s1 -> (s2, s3, s4) -> s5
    s1 = TaskStep(id="s1", name="Step 1", agent_id="mock_agent", action=Action(action_type="op"), dependencies=[], parallelizable=True)
    s2 = TaskStep(id="s2", name="Step 2", agent_id="mock_agent", action=Action(action_type="op"), dependencies=["s1"], parallelizable=True)
    s3 = TaskStep(id="s3", name="Step 3", agent_id="mock_agent", action=Action(action_type="op"), dependencies=["s1"], parallelizable=True)
    s4 = TaskStep(id="s4", name="Step 4", agent_id="mock_agent", action=Action(action_type="op"), dependencies=["s1"], parallelizable=True)
    s5 = TaskStep(id="s5", name="Step 5", agent_id="mock_agent", action=Action(action_type="op"), dependencies=["s2", "s3", "s4"], parallelizable=False)

    plan = TaskPlan(goal="Parallel test", steps=[s1, s2, s3, s4, s5])
    task = Task(goal="Parallel test", plan=plan)

    start_t = time.time()
    res_task = await executor.execute_task(task)
    duration = time.time() - start_t

    assert res_task.status.value == "completed"
    assert agent.max_concurrent >= 2  # Proves parallel execution occurred!
    # Sequential would take 5 * 0.2 = 1.0s. Parallel (3 waves) should take ~0.6s + overhead < 0.9s
    assert duration < 0.95


@pytest.mark.asyncio
async def test_resource_scheduler_concurrency_limiting():
    """Verify ResourceScheduler throttles execution to configured max_parallel_tasks."""
    scheduler = ResourceScheduler(max_parallel_tasks=2)
    executor = ParallelDAGExecutor(resource_scheduler=scheduler)
    agent = SlowMockAgent(delay=0.15)
    executor.register_agent("mock_agent", agent)

    # 4 independent steps, but max_parallel_tasks = 2
    steps = [
        TaskStep(id=f"step_{i}", name=f"Step {i}", agent_id="mock_agent", action=Action(action_type="op"), dependencies=[], parallelizable=True)
        for i in range(4)
    ]
    plan = TaskPlan(goal="Throttle test", steps=steps)
    task = Task(goal="Throttle test", plan=plan)

    res_task = await executor.execute_task(task)
    assert res_task.status.value == "completed"
    assert agent.max_concurrent <= 2  # Never exceeds semaphore limit!


@pytest.mark.asyncio
async def test_task_cancellation():
    """Verify cooperative cancellation halts in-flight execution safely."""
    executor = ParallelDAGExecutor()
    agent = SlowMockAgent(delay=0.5)
    executor.register_agent("mock_agent", agent)

    steps = [
        TaskStep(id=f"step_{i}", name=f"Step {i}", agent_id="mock_agent", action=Action(action_type="op"), dependencies=[], parallelizable=True)
        for i in range(3)
    ]
    plan = TaskPlan(goal="Cancel test", steps=steps)
    task = Task(goal="Cancel test", plan=plan)

    async def cancel_soon():
        await asyncio.sleep(0.1)
        executor.cancel_task(task.id)

    cancel_future = asyncio.create_task(cancel_soon())
    res_task = await executor.execute_task(task)
    await cancel_future

    assert res_task.status.value == "cancelled"


@pytest.mark.asyncio
async def test_approval_gate_in_parallel_executor():
    """Verify that a step marked requires_approval pauses until human decision is made."""
    approval_engine = ApprovalEngine()
    executor = ParallelDAGExecutor(approval_engine=approval_engine)
    agent = SlowMockAgent(delay=0.05)
    executor.register_agent("mock_agent", agent)

    step = TaskStep(
        id="app_step",
        name="Destructive Step",
        agent_id="mock_agent",
        action=Action(action_type="delete"),
        dependencies=[],
        requires_approval=True,
        risk_level=AgentRiskLevel.CRITICAL,
    )
    plan = TaskPlan(goal="Approval test", steps=[step])
    task = Task(goal="Approval test", plan=plan)

    async def approve_soon():
        while not approval_engine.get_pending():
            await asyncio.sleep(0.02)
        req = approval_engine.get_pending()[0]
        approval_engine.resolve_decision(ApprovalDecision(request_id=req.id, decision=ApprovalStatus.APPROVED))

    approve_task = asyncio.create_task(approve_soon())
    res_task = await executor.execute_task(task)
    await approve_task

    assert res_task.status.value == "completed"
    assert step.status.value == "completed"


def test_execution_queue_duplicate_detection():
    queue = ExecutionQueue()
    t1 = Task(goal="Run system backup")
    queue.register_task(t1, priority=TaskPriority.HIGH)

    dup = queue.find_active_duplicate("run system backup")
    assert dup is not None
    assert dup.id == t1.id

    # Once completed, no longer considered an active duplicate
    queue.mark_completed(t1.id)
    assert queue.find_active_duplicate("run system backup") is None


class RecoveryMockAgent:
    """Mock agent that fails on browser.navigate and succeeds on fallback."""

    async def run(self, input_obj, context):
        payload = input_obj.payload or {}
        action = payload.get("action") or payload.get("action_type") or ""
        if "navigate" in str(action) or "browser" in str(action):
            return AgentResult(
                status=AgentStatus.FAILED,
                message="Playwright browser binary not found in headless environment",
                data={"verified": False},
                evidence=[Evidence(type="assertion", source="mock", verified=False)],
            )
        return AgentResult(
            status=AgentStatus.SUCCESS,
            message="Operation completed successfully.",
            data={"verified": True, "status": 200},
            evidence=[Evidence(type="assertion", source="mock", verified=True)],
        )


@pytest.mark.asyncio
async def test_dynamic_replanning_on_step_failure():
    executor = ParallelDAGExecutor(max_replans=2)
    agent = RecoveryMockAgent()
    executor.register_agent("research_agent", agent)
    executor.register_agent("browser_agent", agent)
    executor.register_agent("document_agent", agent)

    s1 = TaskStep(id="s1", name="Init Research", agent_id="research_agent", action=Action(action_type="research.init"), dependencies=[], parallelizable=False)
    s2 = TaskStep(id="s2", name="Browse Details", agent_id="browser_agent", action=Action(action_type="browser.navigate", parameters={"action": "browser.navigate"}), dependencies=["s1"], parallelizable=False)
    s3 = TaskStep(id="s3", name="Summarize", agent_id="document_agent", action=Action(action_type="document.write", parameters={"action": "document.write"}), dependencies=["s2"], parallelizable=False)

    plan = TaskPlan(goal="Browse and summarize", steps=[s1, s2, s3])
    task = Task(goal="Browse and summarize", plan=plan)

    res_task = await executor.execute_task(task)
    assert res_task.status.value == "completed"
    assert getattr(res_task, "_replan_count", 0) == 1
    step_map = {s.id: s for s in res_task.plan.steps}
    assert step_map["s2"].status == StepStatus.SKIPPED
    fallback_steps = [s for s in res_task.plan.steps if "(Fallback)" in s.name]
    assert len(fallback_steps) == 1
    assert fallback_steps[0].status == StepStatus.COMPLETED

