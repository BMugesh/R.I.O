"""GPU Executor for AI acceleration on NVIDIA RTX 4050 (Milestone 4)."""

import asyncio
import logging
import os
import time
from typing import Any, Callable, Dict, Optional

from services.compute.result import ComputeResult
from services.compute.workload import ComputeTarget, Workload
from services.gpu.cuda import detect_gpu
from services.gpu.memory import get_vram_manager

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

logger = logging.getLogger("rio.compute.gpu")


class GPUExecutor:
    """Executes AI acceleration workloads on local NVIDIA GPU with persistent model workers."""

    def __init__(self, device: str = "cuda:0"):
        self.device = device
        self.vram_manager = get_vram_manager()
        self._workers: Dict[str, Callable[[Any], Any]] = {}
        self._initialized = False

    def register_worker(self, workload_type: str, worker: Callable[[Any], Any]) -> None:
        """Register a pre-loaded model inference worker."""
        self._workers[workload_type] = worker
        logger.info(f"GPU worker registered for workload: '{workload_type}'")

    def is_available(self) -> bool:
        """Check if GPU executor has active hardware / backend support."""
        gpu = detect_gpu()
        return bool(gpu.get("available", False))

    async def execute(self, workload: Workload) -> ComputeResult:
        """Execute inference workload on GPU with zero-reload cached workers."""
        start_time = time.perf_counter()
        
        # 1. Verify VRAM availability
        if workload.estimated_memory_mb > 0:
            if not self.vram_manager.can_allocate(workload.estimated_memory_mb):
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                return ComputeResult(
                    output=None,
                    target_used=ComputeTarget.GPU,
                    latency_ms=latency_ms,
                    vram_used_mb=0,
                    success=False,
                    error=f"VRAM ceiling reached (required {workload.estimated_memory_mb} MB, free {self.vram_manager.free_vram_mb} MB)",
                )

        # 2. Lookup registered worker
        worker = self._workers.get(workload.type)
        if not worker:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return ComputeResult(
                output=None,
                target_used=ComputeTarget.GPU,
                latency_ms=latency_ms,
                success=False,
                error=f"No GPU worker registered for workload '{workload.type}'",
            )

        # 3. Execute inference
        try:
            if asyncio.iscoroutinefunction(worker):
                output = await worker(workload.input)
            else:
                loop = asyncio.get_running_loop()
                output = await loop.run_in_executor(None, worker, workload.input)

            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return ComputeResult(
                output=output,
                target_used=ComputeTarget.GPU,
                latency_ms=latency_ms,
                vram_used_mb=workload.estimated_memory_mb,
                success=True,
                metrics={
                    "device": self.device,
                    "vram_headroom_mb": self.vram_manager.free_vram_mb,
                },
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"GPU execution failure for {workload.type}: {e}", exc_info=True)
            return ComputeResult(
                output=None,
                target_used=ComputeTarget.GPU,
                latency_ms=latency_ms,
                success=False,
                error=str(e),
            )
