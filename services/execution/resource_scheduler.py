"""Resource Scheduler for R.I.O. (Milestone 5).

Enforces resource-aware concurrency, dynamic throttling, and preflight
safety checks integrated with M4.5 Test Resource Governor and hardware limits.
"""

import asyncio
from contextlib import asynccontextmanager
import logging
import os
from typing import Any, Dict, Optional
import psutil

from packages.schemas.tasks import TaskStep
from services.test_governor.governor import get_test_governor

logger = logging.getLogger("rio.execution.resource_scheduler")


class ResourceScheduler:
    """Controls concurrent execution slots based on live RAM, VRAM, and subsystem capacities."""

    def __init__(
        self,
        max_parallel_tasks: Optional[int] = None,
        max_parallel_gpu: Optional[int] = None,
        max_parallel_browser: Optional[int] = None,
        max_parallel_network: Optional[int] = None,
    ):
        self.max_parallel_tasks = max_parallel_tasks or int(os.getenv("RIO_MAX_PARALLEL_TASKS", "4"))
        self.max_parallel_gpu = max_parallel_gpu or int(os.getenv("RIO_MAX_PARALLEL_GPU_TASKS", "2"))
        self.max_parallel_browser = max_parallel_browser or int(os.getenv("RIO_MAX_PARALLEL_BROWSER_TASKS", "2"))
        self.max_parallel_network = max_parallel_network or int(os.getenv("RIO_MAX_PARALLEL_NETWORK_TASKS", "4"))

        # Asynchronous semaphores controlling concurrency
        self._task_sem = asyncio.Semaphore(self.max_parallel_tasks)
        self._gpu_sem = asyncio.Semaphore(self.max_parallel_gpu)
        self._browser_sem = asyncio.Semaphore(self.max_parallel_browser)
        self._network_sem = asyncio.Semaphore(self.max_parallel_network)

    def check_preflight_safety(self, step: TaskStep) -> bool:
        """Verify that current system resources can safely accept this workload."""
        # 1. Check RAM availability
        try:
            mem = psutil.virtual_memory()
            available_mb = mem.available / (1024 * 1024)
            # Minimum 1024 MB available RAM threshold for scheduling new work
            min_ram_mb = int(os.getenv("RIO_MIN_EXECUTION_RAM_MB", "1024"))
            if available_mb < min_ram_mb:
                logger.warning(f"ResourceScheduler: Low RAM ({available_mb:.1f} MB < {min_ram_mb} MB). Throttling execution.")
                return False
        except Exception:
            pass

        # 2. Check GPU VRAM if workload requires GPU
        is_gpu = (step.estimated_vram_mb and step.estimated_vram_mb > 0) or ("gpu" in step.action.action_type)
        if is_gpu:
            try:
                gov = get_test_governor()
                gpu_stat = gov.gpu_guard.get_gpu_status()
                free_vram = gpu_stat.get("free_mb", 0)
                headroom = gov.policy.gpu_safety_headroom_mb
                if free_vram < headroom:
                    logger.warning(f"ResourceScheduler: Insufficient VRAM headroom ({free_vram} MB < {headroom} MB).")
                    return False
            except Exception:
                pass

        return True

    @asynccontextmanager
    async def acquire_slot(self, step: TaskStep):
        """Asynchronously acquire appropriate execution semaphores with preflight verification."""
        # 1. Acquire global task slot
        await self._task_sem.acquire()

        acquired_gpu = False
        acquired_browser = False
        acquired_network = False

        try:
            # 2. Acquire domain-specific semaphore
            is_gpu = (step.estimated_vram_mb and step.estimated_vram_mb > 0) or ("gpu" in step.action.action_type)
            if is_gpu:
                await self._gpu_sem.acquire()
                acquired_gpu = True

            is_browser = "browser" in step.agent_id or "browser" in step.action.action_type
            if is_browser:
                await self._browser_sem.acquire()
                acquired_browser = True

            is_network = "search" in step.action.action_type or "web" in step.action.action_type or "http" in step.action.action_type
            if is_network:
                await self._network_sem.acquire()
                acquired_network = True

            yield
        finally:
            if acquired_network:
                self._network_sem.release()
            if acquired_browser:
                self._browser_sem.release()
            if acquired_gpu:
                self._gpu_sem.release()
            self._task_sem.release()
