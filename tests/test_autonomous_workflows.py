"""Tests for R.I.O. Autonomous Compound Workflows & Budget Enforcement (Phase 8).

Validates:
1. Autonomy budget timeout halts runaway execution.
2. Autonomy budget step count limit halts execution.
3. Multi-step compound workflow: LocalSystem telemetry -> FileSystem audit & verification.
4. Multi-step compound workflow: Browser navigation -> Element finding -> Cleanup.
"""

import asyncio
import os
import shutil
import tempfile
import pytest
from packages.schemas.agents import Action, AgentResult, AgentStatus, Evidence
from packages.schemas.input import InputType, RIOInput
from packages.schemas.tasks import (
    AutonomyBudget,
    StepStatus,
    Task,
    TaskPlan,
    TaskStatus,
    TaskStep,
    VerificationStrategy,
)
from services.execution.parallel_executor import ParallelDAGExecutor
from agents.system.agent import LocalSystemAgent
from agents.filesystem.agent import FileSystemAgent
from agents.browser.agent import BrowserAgent


class SlowHangingAgent:
    """Mock agent simulating a slow/stalled tool execution."""

    async def run(self, input_obj: RIOInput, context: dict) -> AgentResult:
        await asyncio.sleep(2.0)
        return AgentResult(
            status=AgentStatus.SUCCESS,
            data={"done": True, "verified": True},
            evidence=[Evidence(type="assertion", source="slow_agent", verified=True, confidence=1.0)],
        )


class FastMockAgent:
    """Mock agent returning fast verifiable result."""

    async def run(self, input_obj: RIOInput, context: dict) -> AgentResult:
        return AgentResult(
            status=AgentStatus.SUCCESS,
            data={"done": True, "verified": True},
            evidence=[Evidence(type="assertion", source="fast_agent", verified=True, confidence=1.0)],
        )


@pytest.mark.asyncio
async def test_autonomy_budget_timeout_halts_execution():
    """Verify that execution times out and halts if runtime exceeds max_runtime_seconds."""
    executor = ParallelDAGExecutor()
    executor.register_agent("slow_agent", SlowHangingAgent())

    plan = TaskPlan(
        goal="Run slow task with short budget",
        steps=[
            TaskStep(
                name="Slow Step",
                agent_id="slow_agent",
                action=Action(action_type="slow_action"),
            )
        ],
    )

    # Budget allows max 0.2 seconds, while agent sleeps for 2.0 seconds
    budget = AutonomyBudget(max_runtime_seconds=0.2, max_total_steps=10)
    task = Task(goal="Run slow task", plan=plan, budget=budget)

    result_task = await executor.execute_task(task)

    assert result_task.status == TaskStatus.FAILED
    assert "budget exceeded" in result_task.error.lower()
    assert "runtime" in result_task.error.lower()


@pytest.mark.asyncio
async def test_autonomy_budget_step_limit_halts_execution():
    """Verify that execution halts if total steps executed reaches max_total_steps."""
    executor = ParallelDAGExecutor()
    executor.register_agent("fast_agent", FastMockAgent())

    step1 = TaskStep(
        id="s1",
        name="Step 1",
        agent_id="fast_agent",
        action=Action(action_type="act1"),
        parallelizable=False,
    )
    step2 = TaskStep(
        id="s2",
        name="Step 2",
        agent_id="fast_agent",
        action=Action(action_type="act2"),
        dependencies=["s1"],
        parallelizable=False,
    )
    step3 = TaskStep(
        id="s3",
        name="Step 3",
        agent_id="fast_agent",
        action=Action(action_type="act3"),
        dependencies=["s2"],
        parallelizable=False,
    )

    plan = TaskPlan(
        goal="Execute 3 steps with 1 step budget",
        steps=[step1, step2, step3],
    )

    # Budget allows only 1 total step
    budget = AutonomyBudget(max_runtime_seconds=10.0, max_total_steps=1)
    task = Task(goal="Execute 3 steps", plan=plan, budget=budget)

    result_task = await executor.execute_task(task)

    assert result_task.status == TaskStatus.FAILED
    assert "budget exceeded" in result_task.error.lower()
    assert "total steps" in result_task.error.lower() or "executed" in result_task.error.lower()


@pytest.mark.asyncio
async def test_compound_workflow_local_system_and_filesystem():
    """Execute a real compound workflow: read system telemetry then write it to a verified file."""
    temp_dir = tempfile.mkdtemp(prefix="rio_workflow_test_")
    report_path = os.path.join(temp_dir, "system_report.txt")

    try:
        sys_agent = LocalSystemAgent()
        fs_agent = FileSystemAgent()

        executor = ParallelDAGExecutor()
        executor.register_agent("local_system_agent", sys_agent)
        executor.register_agent("filesystem_agent", fs_agent)

        step_sys = TaskStep(
            id="sys_info",
            name="Get System Telemetry",
            agent_id="local_system_agent",
            action=Action(action_type="system.summary"),
            verification_strategy=VerificationStrategy(
                strategy_type="assertion",
                expected_state={"verified": True},
            ),
        )

        step_fs = TaskStep(
            id="write_report",
            name="Write Telemetry to Disk",
            agent_id="filesystem_agent",
            action=Action(
                action_type="write_file",
                parameters={"path": report_path, "content": "R.I.O. System Telemetry Verified Execution."},
            ),
            dependencies=["sys_info"],
            verification_strategy=VerificationStrategy(
                strategy_type="file_check",
                expected_state={"path": report_path, "exists": True},
            ),
        )

        plan = TaskPlan(
            goal="Collect system telemetry and write to persistent storage",
            steps=[step_sys, step_fs],
        )

        task = Task(goal="Telemetry Audit Workflow", plan=plan)
        result_task = await executor.execute_task(task)

        assert result_task.status == TaskStatus.COMPLETED
        assert step_sys.status == StepStatus.COMPLETED
        assert step_fs.status == StepStatus.COMPLETED

        # Check physical existence and content
        assert os.path.isfile(report_path)
        with open(report_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "R.I.O. System Telemetry Verified Execution." in content
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_compound_workflow_browser_navigation_and_dom():
    """Execute a real compound workflow with BrowserAgent: navigate to local HTML and find element."""
    browser_agent = BrowserAgent()
    executor = ParallelDAGExecutor()
    executor.register_agent("browser_agent", browser_agent)

    test_html_data_uri = (
        "data:text/html,<html><head><title>RIO Workflow</title></head>"
        "<body><h1>Autonomous RIO</h1><button id='start-btn'>Start Process</button></body></html>"
    )

    step_nav = TaskStep(
        id="nav",
        name="Navigate to Test Page",
        agent_id="browser_agent",
        action=Action(
            action_type="browser.navigate",
            parameters={"url": test_html_data_uri},
        ),
        verification_strategy=VerificationStrategy(
            strategy_type="web_page",
            expected_state={"verified": True},
        ),
    )

    step_find = TaskStep(
        id="find",
        name="Find Start Button",
        agent_id="browser_agent",
        action=Action(
            action_type="browser.find",
            parameters={"selector": "#start-btn"},
        ),
        dependencies=["nav"],
        verification_strategy=VerificationStrategy(
            strategy_type="dom_query",
            expected_state={"selector": "#start-btn"},
        ),
    )

    step_close = TaskStep(
        id="close",
        name="Close Browser",
        agent_id="browser_agent",
        action=Action(action_type="browser.close"),
        dependencies=["find"],
    )

    plan = TaskPlan(
        goal="Navigate to page, find button, and close browser",
        steps=[step_nav, step_find, step_close],
    )

    task = Task(goal="Browser Automation Workflow", plan=plan)

    try:
        result_task = await executor.execute_task(task)
        assert result_task.status == TaskStatus.COMPLETED
        assert step_nav.status == StepStatus.COMPLETED
        assert step_find.status == StepStatus.COMPLETED
        assert step_close.status == StepStatus.COMPLETED
    finally:
        # Guarantee browser is closed
        await browser_agent.close()
