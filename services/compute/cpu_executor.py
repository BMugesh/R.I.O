"""CPU Executor for local OS, control-plane, and fallback workloads in R.I.O."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import os
import time
from typing import Any, Callable, Dict, Optional

from services.compute.result import ComputeResult
from services.compute.workload import ComputeTarget, Workload

logger = logging.getLogger("rio.compute.cpu")


class CPUExecutor:
    """Handles all control plane and fallback computation on host CPU."""

    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="rio-cpu-worker")
        self._handlers: Dict[str, Callable[[Any], Any]] = {}
        if os.getenv("RIO_ENV") == "test":
            try:
                from services.test_governor.governor import get_test_governor
                get_test_governor().thread_tracker.register_pool(self.executor)
            except Exception:
                pass

    def register_handler(self, workload_type: str, handler: Callable[[Any], Any]) -> None:
        """Register a specialized CPU execution function for a workload type."""
        self._handlers[workload_type] = handler

    async def execute(self, workload: Workload) -> ComputeResult:
        """Execute workload on CPU."""
        start_time = time.perf_counter()
        handler = self._handlers.get(workload.type)

        try:
            if handler:
                loop = asyncio.get_running_loop()
                if asyncio.iscoroutinefunction(handler):
                    output = await handler(workload.input)
                else:
                    output = await loop.run_in_executor(self.executor, handler, workload.input)
            else:
                # Default generic processor
                output = self._default_process(workload)

            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return ComputeResult(
                output=output,
                target_used=ComputeTarget.CPU,
                latency_ms=latency_ms,
                vram_used_mb=0,
                success=True,
                metrics={"threads": 4, "mode": "cpu"},
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"CPU execution error for {workload.type}: {e}", exc_info=True)
            return ComputeResult(
                output=None,
                target_used=ComputeTarget.CPU,
                latency_ms=latency_ms,
                success=False,
                error=str(e),
            )

    def _default_process(self, workload: Workload) -> Any:
        """Default fallback handler if no specific handler is registered."""
        if callable(workload.input):
            return workload.input()
        return workload.input

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False)
