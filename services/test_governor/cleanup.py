"""Unified Resource Cleanup Dispatcher (Milestone 4.5).

Coordinates post-test reclamation across browsers, child processes,
thread pools, asyncio tasks, GPU models, and heap garbage collection.
"""

import asyncio
import gc
import logging
from typing import Any, List, Optional, Set

from services.test_governor.gpu_guard import GPUGuard
from services.test_governor.process_tracker import ProcessTracker
from services.test_governor.task_tracker import TaskTracker
from services.test_governor.thread_tracker import ThreadTracker

logger = logging.getLogger("rio.test_governor.cleanup")


class ResourceCleanupDispatcher:
    """Dispatches deterministic teardown for all test-scoped resources."""

    def __init__(
        self,
        process_tracker: Optional[ProcessTracker] = None,
        thread_tracker: Optional[ThreadTracker] = None,
        task_tracker: Optional[TaskTracker] = None,
        gpu_guard: Optional[GPUGuard] = None,
    ):
        self.process_tracker = process_tracker or ProcessTracker()
        self.thread_tracker = thread_tracker or ThreadTracker()
        self.task_tracker = task_tracker or TaskTracker()
        self.gpu_guard = gpu_guard or GPUGuard()
        self._registered_browsers: Set[Any] = set()
        self._registered_contexts: Set[Any] = set()

    def register_browser(self, browser: Any) -> None:
        """Register a Playwright browser or context for guaranteed cleanup."""
        self._registered_browsers.add(browser)

    def register_context(self, context: Any) -> None:
        """Register a Playwright browser context or page."""
        self._registered_contexts.add(context)

    async def cleanup_browsers(self) -> None:
        """Close all registered browser contexts and instances."""
        for ctx in list(self._registered_contexts):
            try:
                if hasattr(ctx, "close"):
                    res = ctx.close()
                    if asyncio.iscoroutine(res):
                        await res
            except Exception as e:
                logger.debug(f"Context close note: {e}")
        self._registered_contexts.clear()

        for browser in list(self._registered_browsers):
            try:
                if hasattr(browser, "close"):
                    res = browser.close()
                    if asyncio.iscoroutine(res):
                        await res
            except Exception as e:
                logger.debug(f"Browser close note: {e}")
        self._registered_browsers.clear()

    async def run_full_cleanup(self, gpu_executor: Optional[Any] = None) -> None:
        """Execute full teardown across all resource domains."""
        # 1. Close browsers
        await self.cleanup_browsers()

        # 2. Cancel and await lingering asyncio tasks
        await self.task_tracker.cleanup_tasks()

        # 3. Shutdown registered thread pools
        self.thread_tracker.shutdown_registered_pools(wait=False)

        # 4. Terminate test-spawned child processes
        self.process_tracker.cleanup_owned_processes(timeout=1.0)

        # 5. Evict GPU models and flush CUDA cache
        self.gpu_guard.cleanup_gpu(executor=gpu_executor)

        # 6. Run generational garbage collection
        gc.collect(2)

    def run_sync_cleanup(self, gpu_executor: Optional[Any] = None) -> None:
        """Synchronous cleanup variant suitable for non-async teardowns."""
        # 1. Synchronous browser cleanup attempt
        for ctx in list(self._registered_contexts):
            try:
                if hasattr(ctx, "close") and not asyncio.iscoroutinefunction(ctx.close):
                    ctx.close()
            except Exception:
                pass
        self._registered_contexts.clear()

        for b in list(self._registered_browsers):
            try:
                if hasattr(b, "close") and not asyncio.iscoroutinefunction(b.close):
                    b.close()
            except Exception:
                pass
        self._registered_browsers.clear()

        # 2. Thread pools
        self.thread_tracker.shutdown_registered_pools(wait=False)

        # 3. Subprocesses
        self.process_tracker.cleanup_owned_processes(timeout=0.5)

        # 4. GPU cache
        self.gpu_guard.cleanup_gpu(executor=gpu_executor)

        # 5. GC
        gc.collect()
