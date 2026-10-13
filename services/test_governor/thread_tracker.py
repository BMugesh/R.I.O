"""Thread Lifecycle and Thread Pool Tracker (Milestone 4.5).

Monitors host thread counts, detects persistent threads surviving test teardown,
and provides deterministic shutdown hooks for thread pools.
"""

from concurrent.futures import ThreadPoolExecutor
import logging
import threading
from typing import List, Optional, Set

logger = logging.getLogger("rio.test_governor.thread")


class ThreadTracker:
    """Tracks active threads and registered thread pools."""

    def __init__(self):
        self._baseline_thread_ids: Set[int] = set()
        self._registered_pools: Set[ThreadPoolExecutor] = set()

    def capture_baseline(self) -> None:
        """Capture currently active thread IDs."""
        self._baseline_thread_ids = {t.ident for t in threading.enumerate() if t.ident is not None}

    def register_pool(self, pool: ThreadPoolExecutor) -> None:
        """Register a ThreadPoolExecutor for automatic test teardown."""
        self._registered_pools.add(pool)

    def get_lingering_threads(self) -> List[threading.Thread]:
        """Return threads created after baseline that are still alive."""
        current = threading.enumerate()
        lingering = []
        for t in current:
            if t.ident not in self._baseline_thread_ids and t.is_alive():
                # Filter out pytest-internal or asyncio-internal threads
                if not t.name.startswith("pytest-") and not t.name.startswith("asyncio_"):
                    lingering.append(t)
        return lingering

    def shutdown_registered_pools(self, wait: bool = False) -> None:
        """Deterministically shut down all registered thread pools."""
        for pool in list(self._registered_pools):
            try:
                pool.shutdown(wait=wait, cancel_futures=True)
            except Exception as e:
                logger.debug(f"ThreadPool shutdown note: {e}")
        self._registered_pools.clear()
