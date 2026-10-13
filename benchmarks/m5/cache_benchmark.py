"""Intelligent Cache Benchmark for R.I.O. (Milestone 5).

Measures cache hit vs miss latency and throughput under policy validation.
"""

import os
import time

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
from services.memory.cache_policy import CacheTier
from services.memory.intelligent_cache import IntelligentCacheManager


def run_benchmark():
    cache = IntelligentCacheManager()
    iterations = 5000

    # Populate cache
    for i in range(100):
        cache.set(f"key_{i}", f"value_{i}", tier=CacheTier.STATIC)

    # 1. Benchmark Hits
    t0 = time.perf_counter()
    for i in range(iterations):
        val = cache.get(f"key_{i % 100}")
    hit_time_ms = (time.perf_counter() - t0) * 1000.0

    # 2. Benchmark Misses
    t1 = time.perf_counter()
    for i in range(iterations):
        val = cache.get(f"missing_{i}")
    miss_time_ms = (time.perf_counter() - t1) * 1000.0

    print("\n" + "=" * 50)
    print("      R.I.O. M5 INTELLIGENT CACHE BENCHMARK")
    print("=" * 50)
    print(f"Iterations:     {iterations}")
    print(f"Hit Latency:    {(hit_time_ms / iterations) * 1000.0:.2f} μs / lookup")
    print(f"Miss Latency:   {(miss_time_ms / iterations) * 1000.0:.2f} μs / lookup")
    print(f"Metrics:        {cache.get_metrics()}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    run_benchmark()
