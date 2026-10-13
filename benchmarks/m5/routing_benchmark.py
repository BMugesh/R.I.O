"""Adaptive Model Routing Benchmark for R.I.O. (Milestone 5).

Measures heuristic scoring throughput and multi-criteria selection latency.
"""

import os
import time

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
from services.model_router.adaptive_router import AdaptiveModelRouter


def run_benchmark():
    router = AdaptiveModelRouter()
    iterations = 1000

    t0 = time.perf_counter()
    for _ in range(iterations):
        router.select_best_model(
            task_type="complex_reasoning",
            complexity="extreme",
            latency_sensitive=False,
            requires_tools=True,
        )
    total_ms = (time.perf_counter() - t0) * 1000.0
    avg_us = (total_ms / iterations) * 1000.0

    print("\n" + "=" * 50)
    print("      R.I.O. M5 ADAPTIVE ROUTING BENCHMARK")
    print("=" * 50)
    print(f"Total Iterations:  {iterations}")
    print(f"Total Time:        {total_ms:.2f} ms")
    print(f"Average Decision:  {avg_us:.2f} μs / routing resolution")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    run_benchmark()
