"""Central Test Resource Governor Facade for R.I.O. (Milestone 4.5).

Orchestrates system RAM, GPU VRAM, subprocess, thread, and asyncio task
governance across the entire test lifecycle.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from services.test_governor.cleanup import ResourceCleanupDispatcher
from services.test_governor.gpu_guard import GPUGuard
from services.test_governor.memory_guard import MemoryGuard
from services.test_governor.policy import TestResourcePolicy
from services.test_governor.process_tracker import ProcessTracker
from services.test_governor.report import TestResourceReporter
from services.test_governor.resource_tracker import ResourceSnapshot, ResourceTracker
from services.test_governor.task_tracker import TaskTracker
from services.test_governor.thread_tracker import ThreadTracker

logger = logging.getLogger("rio.test_governor")


class TestResourceGovernor:
    """The central governor ensuring bounded, resource-safe test execution."""

    __test__ = False

    def __init__(self, policy: Optional[TestResourcePolicy] = None):
        self.policy = policy or TestResourcePolicy.from_env()
        self.tracker = ResourceTracker()
        self.memory_guard = MemoryGuard(policy=self.policy)
        self.gpu_guard = GPUGuard(policy=self.policy)
        self.process_tracker = ProcessTracker()
        self.thread_tracker = ThreadTracker()
        self.task_tracker = TaskTracker()
        self.cleanup = ResourceCleanupDispatcher(
            process_tracker=self.process_tracker,
            thread_tracker=self.thread_tracker,
            task_tracker=self.task_tracker,
            gpu_guard=self.gpu_guard,
        )
        self.reporter = TestResourceReporter()

        self._session_start_snap: Optional[ResourceSnapshot] = None
        self._test_leak_records: Dict[str, Any] = {}

    def start_session(self) -> ResourceSnapshot:
        """Initialize governor session and capture initial machine state."""
        self._session_start_snap = self.tracker.snapshot(include_gpu=True)
        return self._session_start_snap

    def on_test_start(self, test_name: str, markers: Optional[List[str]] = None) -> ResourceSnapshot:
        """Pre-test check: verify RAM and GPU headroom, capture start baselines."""
        # 1. RAM headroom guard
        self.memory_guard.check_memory_safety()

        # 2. GPU headroom guard (only query GPU if marked as gpu/hardware or default)
        is_gpu = markers and ("gpu" in markers or "hardware" in markers)
        if is_gpu:
            self.gpu_guard.check_vram_safety(required_mb=200)

        # 3. Capture baseline state for process and thread tracking
        self.process_tracker.capture_baseline()
        self.thread_tracker.capture_baseline()
        self.task_tracker.capture_baseline()

        # 4. Record test snapshot (lightweight snapshot for pure unit tests)
        return self.tracker.start_test(test_name, include_gpu=bool(is_gpu))

    def on_test_end(
        self,
        test_name: str,
        markers: Optional[List[str]] = None,
        gpu_executor: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Post-test teardown: clean up test-created handles and detect leaks."""
        is_gpu = markers and ("gpu" in markers or "hardware" in markers)

        # 1. Dispatch synchronous cleanup
        self.cleanup.run_sync_cleanup(gpu_executor=gpu_executor)

        # 2. Record end test snapshot & compare
        result = self.tracker.end_test(test_name, include_gpu=bool(is_gpu))
        leaks = result.get("leaks", {})

        if any(leaks.values()):
            self._test_leak_records[test_name] = leaks
            logger.warning(f"Resource leak detected after {test_name}: {leaks}")

        return result

    def finish_session(
        self,
        total_tests: int,
        passed_tests: int,
        failed_tests: int,
    ) -> str:
        """Finalize test session, persist JSON report, and return terminal output."""
        end_snap = self.tracker.snapshot(include_gpu=True)
        start_snap = self._session_start_snap or end_snap

        peaks = self.tracker.session_peaks
        all_leaks = self._test_leak_records

        report_dict = {
            "session_completed_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
            },
            "metrics": {
                "start": start_snap.to_dict(),
                "peak": peaks,
                "end": end_snap.to_dict(),
            },
            "leaks": all_leaks,
            "policy": {
                "min_available_ram_mb": self.policy.min_available_ram_mb,
                "gpu_safety_headroom_mb": self.policy.gpu_safety_headroom_mb,
            },
        }

        # Persist report
        self.reporter.persist_report(report_dict)

        # Format terminal table
        return self.reporter.format_terminal_box(
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            start_snap=start_snap,
            peak_metrics=peaks,
            end_snap=end_snap,
            leak_summary=all_leaks,
        )


# Singleton instance
_governor: Optional[TestResourceGovernor] = None


def get_test_governor() -> TestResourceGovernor:
    """Retrieve the global TestResourceGovernor singleton."""
    global _governor
    if _governor is None:
        _governor = TestResourceGovernor()
    return _governor
