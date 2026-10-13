"""Parallel DAG Execution Benchmark for R.I.O. (Milestone 5).

Compares wall-clock latency of sequential vs parallel DAG execution
on independent workloads to quantify speedup.
"""

import asyncio
import os
import time

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
from packages.schemas.agents import Action, AgentResult, AgentStatus, Evidence
from packages.schemas.tasks import Task, TaskPlan, TaskStep
from services.execution.parallel_executor import ParallelDAGExecutor


class BenchmarkMockAgent:
    """Mock agent introducing deterministic latency to simulate worker execution."""

    def __init__(self, step_delay_seconds: float = 0.2):
        self.step_delay = step_delay_seconds

    async def run(self, input_obj, context):
        await asyncio.sleep(self.step_delay)
        return AgentResult(
            status=AgentStatus.SUCCESS,
            data={"verified": True},
            evidence=[Evidence(type="assertion", source="bench", verified=True, confidence=1.0)],
        )


async def run_benchmark():
    agent = BenchmarkMockAgent(step_delay_seconds=0.2)
    executor = ParallelDAGExecutor()
    executor.register_agent("bench_agent", agent)

    # 1. Sequential Workload (5 dependent steps: s1 -> s2 -> s3 -> s4 -> s5)
    seq_steps = [
        TaskStep(
            id=f"seq_{i}",
            name=f"Sequential Step {i}",
            agent_id="bench_agent",
            action=Action(action_type="op"),
            dependencies=[f"seq_{i-1}"] if i > 0 else [],
            parallelizable=False,
        )
        for i in range(5)
    ]
    seq_plan = TaskPlan(goal="Sequential Benchmark", steps=seq_steps)
    seq_task = Task(goal="Sequential Benchmark", plan=seq_plan)

    t0 = time.time()
    await executor.execute_task(seq_task)
    seq_duration = time.time() - t0

    # 2. Parallel Workload (Wave DAG: root -> [p1, p2, p3] -> merge)
    p_root = TaskStep(id="p_root", name="Root Step", agent_id="bench_agent", action=Action(action_type="op"), dependencies=[], parallelizable=True)
    p1 = TaskStep(id="p1", name="Parallel 1", agent_id="bench_agent", action=Action(action_type="op"), dependencies=["p_root"], parallelizable=True)
    p2 = TaskStep(id="p2", name="Parallel 2", agent_id="bench_agent", action=Action(action_type="op"), dependencies=["p_root"], parallelizable=True)
    p3 = TaskStep(id="p3", name="Parallel 3", agent_id="bench_agent", action=Action(action_type="op"), dependencies=["p_root"], parallelizable=True)
    p_merge = TaskStep(id="p_merge", name="Merge Step", agent_id="bench_agent", action=Action(action_type="op"), dependencies=["p1", "p2", "p3"], parallelizable=False)

    par_steps = [p_root, p1, p2, p3, p_merge]
    par_plan = TaskPlan(goal="Parallel Benchmark", steps=par_steps)
    par_task = Task(goal="Parallel Benchmark", plan=par_plan)

    t1 = time.time()
    await executor.execute_task(par_task)
    par_duration = time.time() - t1

    speedup = seq_duration / par_duration if par_duration > 0 else 1.0

    print("\n" + "=" * 50)
    print("      R.I.O. M5 PARALLEL EXECUTION BENCHMARK")
    print("=" * 50)
    print(f"Sequential DAG Latency:  {seq_duration * 1000.0:.2f} ms (5 steps)")
    print(f"Parallel DAG Latency:    {par_duration * 1000.0:.2f} ms (5 steps, 3 parallel)")
    print(f"Parallel Speedup Factor: {speedup:.2f}x")
    print("=" * 50 + "\n")
    return {
        "sequential_ms": seq_duration * 1000.0,
        "parallel_ms": par_duration * 1000.0,
        "speedup": speedup,
    }


if __name__ == "__main__":
    asyncio.run(run_benchmark())
