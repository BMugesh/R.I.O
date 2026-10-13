"""Unit and Integration Tests for R.I.O. Test Resource Governor (Milestone 4.5).

Covers all 18 core requirements:
1. RAM snapshot
2. GPU snapshot
3. Thread snapshot
4. Process snapshot
5. Asyncio task tracking
6. Leak detection
7. Resource policy
8. RAM warning
9. RAM critical handling
10. GPU VRAM guard
11. GPU cleanup
12. Browser cleanup
13. Background task cleanup
14. Subprocess ownership
15. Report generation
16. Environment configuration
17. Safe shutdown
18. No false-positive leak detection
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import threading
import pytest

from services.compute.gpu_executor import GPUExecutor
from services.test_governor.cleanup import ResourceCleanupDispatcher
from services.test_governor.governor import TestResourceGovernor, get_test_governor
from services.test_governor.gpu_guard import GPUGuard, GPUVRAMCriticalError
from services.test_governor.memory_guard import MemoryGuard, ResourceCriticalError
from services.test_governor.policy import TestResourcePolicy
from services.test_governor.process_tracker import ProcessTracker
from services.test_governor.report import TestResourceReporter
from services.test_governor.resource_tracker import ResourceSnapshot, ResourceTracker
from services.test_governor.task_tracker import TaskTracker
from services.test_governor.thread_tracker import ThreadTracker


# 1. RAM Snapshot
@pytest.mark.unit
def test_ram_snapshot():
    tracker = ResourceTracker()
    snap = tracker.snapshot(include_gpu=False)
    assert snap.ram_total_mb > 0
    assert snap.ram_available_mb > 0
    assert snap.process_rss_mb > 0
    assert snap.process_peak_rss_mb >= snap.process_rss_mb


# 2. GPU Snapshot
@pytest.mark.unit
def test_gpu_snapshot():
    tracker = ResourceTracker()
    snap = tracker.snapshot(include_gpu=True)
    assert snap.timestamp is not None
    # If GPU is present, vram total must be positive
    if snap.gpu_total_mb is not None:
        assert snap.gpu_total_mb > 0
        assert snap.gpu_free_mb is not None
        assert snap.gpu_used_mb is not None


# 3. Thread Snapshot
@pytest.mark.unit
def test_thread_snapshot():
    tracker = ResourceTracker()
    snap = tracker.snapshot(include_gpu=False)
    assert snap.thread_count >= 1
    assert len(snap.thread_names) == snap.thread_count
    assert threading.current_thread().name in snap.thread_names


# 4. Process Snapshot
@pytest.mark.unit
def test_process_snapshot():
    tracker = ResourceTracker()
    snap = tracker.snapshot(include_gpu=False)
    assert snap.process_count >= 0
    assert isinstance(snap.child_pids, list)


# 5. Asyncio Task Tracking
@pytest.mark.asyncio
@pytest.mark.unit
async def test_asyncio_task_tracking():
    tracker = TaskTracker()
    tracker.capture_baseline()

    # Create a background test task
    async def dummy_work():
        await asyncio.sleep(10)

    task = asyncio.create_task(dummy_work(), name="test-dummy-task-01")
    tracker.register_task(task)

    lingering = tracker.get_lingering_tasks()
    assert any(t.get_name() == "test-dummy-task-01" for t in lingering)

    # Cleanup
    cancelled = await tracker.cleanup_tasks()
    assert "test-dummy-task-01" in cancelled
    assert task.cancelled() or task.done()


# 6. Leak Detection
@pytest.mark.unit
def test_leak_detection():
    tracker = ResourceTracker()
    start = ResourceSnapshot(
        timestamp="2026-09-12T00:00:00Z",
        ram_total_mb=16000.0,
        ram_available_mb=8000.0,
        process_rss_mb=500.0,
        process_peak_rss_mb=500.0,
        gpu_total_mb=6000.0,
        gpu_used_mb=500.0,
        gpu_free_mb=5500.0,
        thread_count=5,
        process_count=0,
        asyncio_task_count=0,
        thread_names=["MainThread", "Worker-1"],
        child_pids=[],
        active_task_names=[],
    )
    # End snapshot with simulated leaks
    end = ResourceSnapshot(
        timestamp="2026-09-12T00:01:00Z",
        ram_total_mb=16000.0,
        ram_available_mb=7000.0,
        process_rss_mb=1000.0,  # +500 MB
        process_peak_rss_mb=1000.0,
        gpu_total_mb=6000.0,
        gpu_used_mb=800.0,  # +300 MB
        gpu_free_mb=5200.0,
        thread_count=7,
        process_count=1,
        asyncio_task_count=1,
        thread_names=["MainThread", "Worker-1", "leaked-worker-thread"],
        child_pids=[9999],
        active_task_names=["leaked-coroutine"],
    )

    leaks = tracker.detect_leaks(start, end)
    assert "threads" in leaks
    assert "leaked-worker-thread" in leaks["threads"]
    assert "processes" in leaks
    assert 9999 in leaks["processes"]
    assert "asyncio_tasks" in leaks
    assert "leaked-coroutine" in leaks["asyncio_tasks"]
    assert "vram_mb" in leaks
    assert leaks["vram_mb"] == 300.0
    assert "rss_mb" in leaks
    assert leaks["rss_mb"] == 500.0


# 7. Resource Policy Thresholds
@pytest.mark.unit
def test_resource_policy():
    policy = TestResourcePolicy(
        min_available_ram_mb=2048,
        ram_warning_percent=85.0,
        ram_critical_percent=92.0,
        gpu_safety_headroom_mb=800,
    )
    # 3000 MB free out of 16000 MB = ~81.25% used -> SAFE
    assert policy.is_ram_critical(available_mb=3000, total_mb=16000) is False
    assert policy.is_ram_warning(available_mb=3000, total_mb=16000) is False

    # 1000 MB free out of 16000 MB = < 2048 min -> CRITICAL
    assert policy.is_ram_critical(available_mb=1000, total_mb=16000) is True

    # 93% used -> CRITICAL
    assert policy.is_ram_critical(available_mb=1120, total_mb=16000) is True

    # VRAM headroom: 700 MB free < 800 MB safety headroom -> unsafe
    assert policy.is_vram_safe(free_vram_mb=700) is False
    assert policy.is_vram_safe(free_vram_mb=1500) is True


# 8. RAM Warning
@pytest.mark.unit
def test_ram_warning():
    policy = TestResourcePolicy(ram_warning_percent=80.0, min_available_ram_mb=1000)
    # 2500 MB free out of 16000 MB = 84.3% used -> Warning true, Critical false
    assert policy.is_ram_warning(available_mb=2500, total_mb=16000) is True
    assert policy.is_ram_critical(available_mb=2500, total_mb=16000) is False


# 9. RAM Critical Handling & Safety Stop
@pytest.mark.unit
def test_ram_critical_handling():
    # Configure an artificially high minimum RAM threshold to trigger critical stop
    critical_policy = TestResourcePolicy(min_available_ram_mb=999999)
    guard = MemoryGuard(policy=critical_policy)

    with pytest.raises(ResourceCriticalError) as exc:
        guard.check_memory_safety()
    assert "RESOURCE SAFETY STOP" in str(exc.value)


# 10. GPU VRAM Guard Headroom Validation
@pytest.mark.unit
def test_gpu_vram_guard():
    guard = GPUGuard()
    status = guard.get_gpu_status()
    assert "status" in status
    assert status["status"] in ("SAFE", "CAUTION", "CRITICAL", "NO_GPU", "UNKNOWN")


# 11. GPU Cleanup
@pytest.mark.unit
def test_gpu_cleanup():
    executor = GPUExecutor()
    executor.register_worker("test_workload", lambda x: x * 2)
    assert "test_workload" in executor._workers

    guard = GPUGuard()
    guard.cleanup_gpu(executor=executor)
    assert len(executor._workers) == 0


# 12. Browser Cleanup
@pytest.mark.asyncio
@pytest.mark.unit
async def test_browser_cleanup():
    class MockBrowser:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    mock_b = MockBrowser()
    cleanup = ResourceCleanupDispatcher()
    cleanup.register_browser(mock_b)

    await cleanup.cleanup_browsers()
    assert mock_b.closed is True


# 13. Background Task Cleanup
@pytest.mark.asyncio
@pytest.mark.unit
async def test_background_task_cleanup():
    tracker = TaskTracker()

    async def long_running_coroutine():
        await asyncio.sleep(30)

    task = asyncio.create_task(long_running_coroutine(), name="test-bg-task-99")
    tracker.register_task(task)

    cancelled = await tracker.cleanup_tasks()
    assert "test-bg-task-99" in cancelled
    assert task.done()


# 14. Subprocess Ownership & Reaping
@pytest.mark.unit
def test_subprocess_ownership():
    tracker = ProcessTracker()
    tracker.capture_baseline()

    # Spawn a fast Python sleep process
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    tracker.register_process(proc)

    assert proc.poll() is None
    terminated = tracker.cleanup_owned_processes(timeout=0.5)

    assert proc.pid in terminated
    assert proc.poll() is not None


# 15. Report Generation & JSON Persistence
@pytest.mark.unit
def test_report_generation(tmp_path):
    reporter = TestResourceReporter(reports_dir=tmp_path)
    start_snap = ResourceSnapshot(
        timestamp="2026-09-12T00:00:00Z",
        ram_total_mb=16000.0,
        ram_available_mb=8000.0,
        process_rss_mb=500.0,
        process_peak_rss_mb=500.0,
        gpu_total_mb=6144.0,
        gpu_used_mb=500.0,
        gpu_free_mb=5644.0,
        thread_count=10,
        process_count=1,
        asyncio_task_count=2,
    )
    end_snap = ResourceSnapshot(
        timestamp="2026-09-12T00:01:00Z",
        ram_total_mb=16000.0,
        ram_available_mb=7950.0,
        process_rss_mb=510.0,
        process_peak_rss_mb=550.0,
        gpu_total_mb=6144.0,
        gpu_used_mb=510.0,
        gpu_free_mb=5634.0,
        thread_count=10,
        process_count=1,
        asyncio_task_count=2,
    )

    box = reporter.format_terminal_box(
        total_tests=136,
        passed_tests=136,
        failed_tests=0,
        start_snap=start_snap,
        peak_metrics={"peak_rss_mb": 550.0, "peak_vram_mb": 600.0, "peak_threads": 12, "peak_processes": 1, "peak_tasks": 3},
        end_snap=end_snap,
        leak_summary={},
    )
    assert "R.I.O. TEST RESOURCE REPORT" in box
    assert "Passed                136" in box
    assert "✓ RAM recovered" in box

    report_dict = {"summary": {"total": 136, "passed": 136, "failed": 0}}
    p = reporter.persist_report(report_dict)
    assert p.exists()
    assert (tmp_path / "test_resources_latest.json").exists()


# 16. Environment Configuration Overrides
@pytest.mark.unit
def test_environment_configuration(monkeypatch):
    monkeypatch.setenv("RIO_TEST_MIN_RAM_MB", "4096")
    monkeypatch.setenv("RIO_TEST_RAM_WARNING_PERCENT", "75.0")
    monkeypatch.setenv("RIO_TEST_RAM_CRITICAL_PERCENT", "88.0")
    monkeypatch.setenv("RIO_TEST_GPU_HEADROOM_MB", "1200")

    policy = TestResourcePolicy.from_env()
    assert policy.min_available_ram_mb == 4096
    assert policy.ram_warning_percent == 75.0
    assert policy.ram_critical_percent == 88.0
    assert policy.gpu_safety_headroom_mb == 1200


# 17. Safe Shutdown
@pytest.mark.unit
def test_safe_shutdown():
    gov = TestResourceGovernor()
    gov.start_session()
    # Register dummy thread pool
    pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="test-gov-pool")
    gov.thread_tracker.register_pool(pool)

    # Perform cleanup
    gov.cleanup.run_sync_cleanup()
    # Ensure pool is shut down
    with pytest.raises(RuntimeError):
        pool.submit(lambda: 42)


# 18. No False-Positive Leak Detection
@pytest.mark.unit
def test_no_false_positive_leak_detection():
    tracker = ResourceTracker()
    snap1 = tracker.snapshot(include_gpu=False)
    # Immediate second snapshot should report 0 leaks
    snap2 = tracker.snapshot(include_gpu=False)
    leaks = tracker.detect_leaks(snap1, snap2)
    assert len(leaks) == 0
