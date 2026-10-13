"""Memory Safety Guard for R.I.O. Test Infrastructure (Milestone 4.5).

Prevents test executions from starving host Windows operating system of RAM.
Enforces minimum available RAM ceilings and graceful safety pauses.
"""

import gc
import logging
from typing import Optional
import psutil

from services.test_governor.policy import TestResourcePolicy

logger = logging.getLogger("rio.test_governor.memory")


class ResourceCriticalError(RuntimeError):
    """Raised when host system resources are dangerously exhausted."""
    pass


class MemoryGuard:
    """Monitors system memory and enforces pre-test thresholds."""

    def __init__(self, policy: Optional[TestResourcePolicy] = None):
        self.policy = policy or TestResourcePolicy.from_env()

    def check_memory_safety(self) -> None:
        """Inspect system memory before running test.
        Raises ResourceCriticalError if memory cannot be safely recovered.
        """
        vm = psutil.virtual_memory()
        ram_total = vm.total / (1024.0 * 1024.0)
        ram_avail = vm.available / (1024.0 * 1024.0)

        # Warning threshold
        if self.policy.is_ram_warning(ram_avail, ram_total):
            used_pct = ((ram_total - ram_avail) / ram_total) * 100.0
            logger.warning(
                f"[RESOURCE WARNING] Host RAM utilization elevated: {used_pct:.1f}% "
                f"(Available: {ram_avail:.0f} MB / {ram_total:.0f} MB)"
            )

        # Critical threshold
        if self.policy.is_ram_critical(ram_avail, ram_total):
            logger.error(
                f"[RESOURCE CRITICAL] Available RAM ({ram_avail:.0f} MB) below minimum "
                f"({self.policy.min_available_ram_mb} MB). Triggering emergency GC cleanup..."
            )
            # Attempt recovery
            gc.collect(2)
            vm_after = psutil.virtual_memory()
            ram_avail_after = vm_after.available / (1024.0 * 1024.0)

            if self.policy.is_ram_critical(ram_avail_after, ram_total):
                msg = (
                    f"RESOURCE SAFETY STOP: Host RAM critical ({ram_avail_after:.0f} MB available, "
                    f"minimum required {self.policy.min_available_ram_mb} MB). "
                    "Aborting test to protect Windows responsiveness."
                )
                logger.critical(msg)
                raise ResourceCriticalError(msg)
            else:
                logger.info(f"[RESOURCE RECOVERED] RAM restored to {ram_avail_after:.0f} MB after GC.")

    def run_garbage_collection(self) -> int:
        """Perform generational garbage collection."""
        return gc.collect()
