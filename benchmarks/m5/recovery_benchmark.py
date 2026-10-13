"""Failure Recovery & Replanning Benchmark for R.I.O. (Milestone 5).

Measures error classification, retry calculation, fallback evaluation,
and dynamic DAG replanning latency.
"""

import copy
import os
import time
import uuid

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
from packages.schemas.agents import Action, AgentRiskLevel
from packages.schemas.tasks import StepStatus, Task, TaskPlan, TaskStep
from services.recovery.classifier import FailureClassifier, FailureType
from services.recovery.fallback import FallbackManager
from services.recovery.replanner import Replanner
from services.recovery.retry_policy import RetryPolicy


def run_benchmark():
    retry_policy = RetryPolicy(max_retries=3)
    iterations = 5000

    print("\n" + "=" * 55)
    print("      R.I.O. M5 RECOVERY & REPLANNING BENCHMARK")
    print("=" * 55)

    # 1. Error Classification Benchmark
    sample_errors = [
        RuntimeError("CUDA error: out of memory. Tried to allocate 2.00 GiB"),
        TimeoutError("Connection timed out after 5000ms"),
        PermissionError("Access denied: approval required for system write"),
        ValueError("Validation error: malformed JSON input"),
    ]

    t0 = time.perf_counter()
    for i in range(iterations):
        err = sample_errors[i % len(sample_errors)]
        FailureClassifier.classify(err)
    class_ms = (time.perf_counter() - t0) * 1000.0
    avg_class_us = (class_ms / iterations) * 1000.0
    print(f"Error Classification:     {avg_class_us:.2f} μs / classification")

    # 2. Fallback Evaluation Benchmark
    t0 = time.perf_counter()
    for _ in range(iterations):
        FallbackManager.get_compute_fallback("gpu")
        FallbackManager.get_model_fallback("openai/gpt-oss-120b")
        FallbackManager.get_tool_fallback("browser.navigate")
    fallback_ms = (time.perf_counter() - t0) * 1000.0
    avg_fallback_us = (fallback_ms / iterations) * 1000.0
    print(f"Fallback Resolution:      {avg_fallback_us:.2f} μs / resolution")

    # 3. Dynamic DAG Replanning Latency
    replan_iterations = 1000
    step1_id = str(uuid.uuid4())
    step2_id = str(uuid.uuid4())
    step3_id = str(uuid.uuid4())

    base_plan = TaskPlan(
        id=str(uuid.uuid4()),
        goal="Benchmark replanning workflow",
        steps=[
            TaskStep(
                id=step1_id,
                name="Fetch data",
                description="Fetch preliminary data",
                agent_id="agent_1",
                action=Action(action_type="data.fetch", parameters={}),
                status=StepStatus.COMPLETED,
            ),
            TaskStep(
                id=step2_id,
                name="Launch app",
                description="Launch target application",
                agent_id="agent_2",
                action=Action(action_type="device.launch_app", parameters={"app": "test"}),
                dependencies=[step1_id],
                status=StepStatus.FAILED,
                error="App launch failed",
            ),
            TaskStep(
                id=step3_id,
                name="Verify state",
                description="Verify state after launch",
                agent_id="agent_3",
                action=Action(action_type="state.verify", parameters={}),
                dependencies=[step2_id],
                status=StepStatus.PENDING,
            ),
        ],
    )
    base_task = Task(goal="Benchmark replanning workflow", plan=base_plan)

    t0 = time.perf_counter()
    for _ in range(replan_iterations):
        # Create shallow copy of plan steps for benchmark purity
        task_copy = Task(
            goal=base_task.goal,
            plan=TaskPlan(
                id=str(uuid.uuid4()),
                goal=base_plan.goal,
                steps=[s.model_copy(deep=True) for s in base_plan.steps],
            ),
        )
        Replanner.replan_failed_step(
            task=task_copy,
            failed_step=task_copy.plan.steps[1],
            failure_reason="Device unresponsive",
        )
    replan_ms = (time.perf_counter() - t0) * 1000.0
    avg_replan_us = (replan_ms / replan_iterations) * 1000.0
    print(f"Dynamic DAG Replanning:   {avg_replan_us:.2f} μs / replan")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    run_benchmark()
