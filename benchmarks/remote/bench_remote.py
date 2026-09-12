"""Remote Cloud Benchmark for R.I.O. (Milestone 4)."""

import time
from typing import Any, Dict


async def benchmark_remote_inference() -> Dict[str, Any]:
    """Measure latency of remote cloud invocation."""
    from services.compute.remote_executor import RemoteExecutor
    from services.compute.workload import Workload

    executor = RemoteExecutor()
    workload = Workload(
        type="complex_reasoning",  # type: ignore
        input="Ping latency test",
        latency="normal",
        privacy="remote_allowed",
    )

    t0 = time.perf_counter()
    res = await executor.execute(workload)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    return {
        "workload": "remote_groq",
        "latency_ms": round(elapsed_ms, 2),
        "success": res.success,
    }
