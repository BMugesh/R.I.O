"""Planning Latency Benchmark for R.I.O. (Milestone 5).

Measures task analysis, dependency decomposition, validation, and optimization latency.
"""

import asyncio
import os
import time

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
from services.planning.planner import IntelligentPlanner


async def run_benchmark():
    planner = IntelligentPlanner()

    scenarios = [
        ("Simple", "Open Notepad"),
        ("Moderate", "Take a screenshot and summarize recent notifications"),
        ("Complex Parallel", "Research the latest NVIDIA GPU, compare it with my laptop and create a report."),
    ]

    print("\n" + "=" * 50)
    print("      R.I.O. M5 PLANNING LATENCY BENCHMARK")
    print("=" * 50)

    for name, goal in scenarios:
        t0 = time.perf_counter()
        plan = await planner.plan(goal)
        dur_ms = (time.perf_counter() - t0) * 1000.0
        print(f"[{name:<16}] {dur_ms:.2f} ms | Steps: {len(plan.steps)} | Max Concurrency: {plan.max_parallelism}")

    print("=" * 50 + "\n")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
