"""Autonomous Runtime Loop Benchmark for R.I.O. (Milestone 5).

Measures autonomy budget enforcement, world state updates, and controller throughput.
"""

import asyncio
import os
import time

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
from services.autonomy.budget import AutonomyBudget
from services.autonomy.controller import AutonomyController
from services.autonomy.world_state import WorldState


def run_benchmark():
    budget = AutonomyBudget(max_runtime_ms=100000, max_actions=10000)
    world_state = WorldState()
    iterations = 10000

    print("\n" + "=" * 55)
    print("      R.I.O. M5 AUTONOMOUS RUNTIME BENCHMARK")
    print("=" * 55)

    # 1. Budget Evaluation Latency
    t0 = time.perf_counter()
    for _ in range(iterations):
        budget.can_continue()
        budget.record_action(duration_ms=1)
    budget_ms = (time.perf_counter() - t0) * 1000.0
    avg_budget_us = (budget_ms / iterations) * 1000.0
    print(f"Budget Check & Update:    {avg_budget_us:.2f} μs / cycle")

    # 2. World State Update Throughput
    t0 = time.perf_counter()
    for i in range(iterations):
        task_id = f"task_{i % 100}"
        world_state.update_task_status(task_id, "running")
        world_state.update_resource(ram_mb=8192.0, vram_mb=4096.0)
        world_state.update_task_status(task_id, "completed")
    ws_ms = (time.perf_counter() - t0) * 1000.0
    avg_ws_us = (ws_ms / iterations) * 1000.0
    print(f"World State Observation:  {avg_ws_us:.2f} μs / state update")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    run_benchmark()
