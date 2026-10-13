"""Resource Tracking and Snapshot Subsystem (Milestone 4.5).

Captures high-fidelity snapshots of RAM, VRAM, threads, child processes,
and asyncio tasks before and after tests to detect leaks.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Set
import psutil

try:
    import torch
except ImportError:
    torch = None

from services.gpu.cuda import detect_gpu
from services.gpu.memory import get_vram_manager

logger = logging.getLogger("rio.test_governor.tracker")


@dataclass
class ResourceSnapshot:
    """Standardized point-in-time resource snapshot."""

    timestamp: str
    ram_total_mb: float
    ram_available_mb: float
    process_rss_mb: float
    process_peak_rss_mb: float

    gpu_total_mb: Optional[float]
    gpu_used_mb: Optional[float]
    gpu_free_mb: Optional[float]

    thread_count: int
    process_count: int
    asyncio_task_count: int

    thread_names: List[str] = field(default_factory=list)
    child_pids: List[int] = field(default_factory=list)
    active_task_names: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "ram_total_mb": round(self.ram_total_mb, 2),
            "ram_available_mb": round(self.ram_available_mb, 2),
            "process_rss_mb": round(self.process_rss_mb, 2),
            "process_peak_rss_mb": round(self.process_peak_rss_mb, 2),
            "gpu_total_mb": round(self.gpu_total_mb, 2) if self.gpu_total_mb is not None else None,
            "gpu_used_mb": round(self.gpu_used_mb, 2) if self.gpu_used_mb is not None else None,
            "gpu_free_mb": round(self.gpu_free_mb, 2) if self.gpu_free_mb is not None else None,
            "thread_count": self.thread_count,
            "process_count": self.process_count,
            "asyncio_task_count": self.asyncio_task_count,
            "thread_names": self.thread_names,
            "child_pids": self.child_pids,
            "active_task_names": self.active_task_names,
        }


class ResourceTracker:
    """Tracks and compares resource usage across test execution boundaries."""

    def __init__(self):
        self._process = psutil.Process(os.getpid())
        self._vram_mgr = get_vram_manager()
        self._start_snapshots: Dict[str, ResourceSnapshot] = {}
        self._session_peak_rss_mb: float = 0.0
        self._session_peak_vram_mb: float = 0.0
        self._session_peak_threads: int = 0
        self._session_peak_processes: int = 0
        self._session_peak_tasks: int = 0

    def snapshot(self, include_gpu: bool = True) -> ResourceSnapshot:
        """Capture current resource utilization snapshot."""
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. System RAM
        vm = psutil.virtual_memory()
        ram_total = vm.total / (1024.0 * 1024.0)
        ram_avail = vm.available / (1024.0 * 1024.0)

        mem_info = self._process.memory_info()
        rss_mb = mem_info.rss / (1024.0 * 1024.0)
        # Windows peak working set, or rss fallback
        peak_rss_mb = getattr(mem_info, "peak_wset", mem_info.rss) / (1024.0 * 1024.0)

        if rss_mb > self._session_peak_rss_mb:
            self._session_peak_rss_mb = rss_mb

        # 2. GPU VRAM
        gpu_total: Optional[float] = None
        gpu_used: Optional[float] = None
        gpu_free: Optional[float] = None

        if include_gpu:
            try:
                if torch is not None and torch.cuda.is_available():
                    dev_idx = torch.cuda.current_device()
                    gpu_total = torch.cuda.get_device_properties(dev_idx).total_memory / (1024.0 * 1024.0)
                    gpu_used = torch.cuda.memory_allocated(dev_idx) / (1024.0 * 1024.0)
                    gpu_free = gpu_total - gpu_used
                else:
                    gpu_info = detect_gpu()
                    if gpu_info.get("available"):
                        gpu_total = float(gpu_info.get("vram_total_mb", 6141))
                        gpu_used = float(gpu_info.get("vram_used_mb", 0))
                        gpu_free = float(gpu_info.get("vram_free_mb", gpu_total))
            except Exception as e:
                logger.debug(f"GPU snapshot query note: {e}")

        if gpu_used is not None and gpu_used > self._session_peak_vram_mb:
            self._session_peak_vram_mb = gpu_used

        # 3. Threads
        live_threads = threading.enumerate()
        thread_count = len(live_threads)
        thread_names = [t.name for t in live_threads]

        if thread_count > self._session_peak_threads:
            self._session_peak_threads = thread_count

        # 4. Child Processes
        try:
            children = self._process.children(recursive=True)
            child_pids = [c.pid for c in children if c.is_running()]
            process_count = len(child_pids)
        except Exception:
            child_pids = []
            process_count = 0

        if process_count > self._session_peak_processes:
            self._session_peak_processes = process_count

        # 5. Asyncio Tasks
        task_count = 0
        task_names = []
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                all_t = asyncio.all_tasks(loop)
                task_count = len(all_t)
                task_names = [t.get_name() for t in all_t]
        except RuntimeError:
            pass

        if task_count > self._session_peak_tasks:
            self._session_peak_tasks = task_count

        return ResourceSnapshot(
            timestamp=now_iso,
            ram_total_mb=ram_total,
            ram_available_mb=ram_avail,
            process_rss_mb=rss_mb,
            process_peak_rss_mb=peak_rss_mb,
            gpu_total_mb=gpu_total,
            gpu_used_mb=gpu_used,
            gpu_free_mb=gpu_free,
            thread_count=thread_count,
            process_count=process_count,
            asyncio_task_count=task_count,
            thread_names=thread_names,
            child_pids=child_pids,
            active_task_names=task_names,
        )

    def start_test(self, test_name: str, include_gpu: bool = True) -> ResourceSnapshot:
        """Record baseline snapshot before test begins."""
        snap = self.snapshot(include_gpu=include_gpu)
        self._start_snapshots[test_name] = snap
        return snap

    def end_test(self, test_name: str, include_gpu: bool = True) -> Dict[str, Any]:
        """Record end snapshot and evaluate test diff."""
        start = self._start_snapshots.pop(test_name, None)
        end = self.snapshot(include_gpu=include_gpu)

        if not start:
            return {"test": test_name, "start": None, "end": end.to_dict(), "diff": {}, "leaks": {}}

        diff = self.compare(start, end)
        leaks = self.detect_leaks(start, end)
        return {
            "test": test_name,
            "start": start.to_dict(),
            "end": end.to_dict(),
            "diff": diff,
            "leaks": leaks,
        }

    def compare(self, start: ResourceSnapshot, end: ResourceSnapshot) -> Dict[str, Any]:
        """Compute deltas between two snapshots."""
        return {
            "delta_rss_mb": round(end.process_rss_mb - start.process_rss_mb, 2),
            "delta_ram_available_mb": round(end.ram_available_mb - start.ram_available_mb, 2),
            "delta_vram_used_mb": (
                round(end.gpu_used_mb - start.gpu_used_mb, 2)
                if (end.gpu_used_mb is not None and start.gpu_used_mb is not None)
                else 0.0
            ),
            "delta_threads": end.thread_count - start.thread_count,
            "delta_processes": end.process_count - start.process_count,
            "delta_tasks": end.asyncio_task_count - start.asyncio_task_count,
        }

    def detect_leaks(self, start: ResourceSnapshot, end: ResourceSnapshot) -> Dict[str, Any]:
        """Detect any lingering resources beyond baseline."""
        leaks: Dict[str, Any] = {}

        # 1. Thread leak
        new_threads = set(end.thread_names) - set(start.thread_names)
        # Filter out transient internal pytest/asyncio threads
        persisted_threads = [t for t in new_threads if not t.startswith("pytest-") and not t.startswith("asyncio_")]
        if persisted_threads:
            leaks["threads"] = persisted_threads

        # 2. Child process leak
        new_pids = set(end.child_pids) - set(start.child_pids)
        if new_pids:
            leaks["processes"] = list(new_pids)

        # 3. Asyncio tasks leak
        if end.asyncio_task_count > start.asyncio_task_count:
            new_tasks = set(end.active_task_names) - set(start.active_task_names)
            if new_tasks:
                leaks["asyncio_tasks"] = list(new_tasks)

        # 4. VRAM leak (threshold: > 150 MB lingering allocation)
        if (
            start.gpu_used_mb is not None
            and end.gpu_used_mb is not None
            and (end.gpu_used_mb - start.gpu_used_mb) > 150.0
        ):
            leaks["vram_mb"] = round(end.gpu_used_mb - start.gpu_used_mb, 2)

        # 5. Process RSS growth warning (threshold: > 400 MB growth in a single test)
        rss_growth = end.process_rss_mb - start.process_rss_mb
        if rss_growth > 400.0:
            leaks["rss_mb"] = round(rss_growth, 2)

        return leaks

    @property
    def session_peaks(self) -> Dict[str, Any]:
        return {
            "peak_rss_mb": round(self._session_peak_rss_mb, 2),
            "peak_vram_mb": round(self._session_peak_vram_mb, 2),
            "peak_threads": self._session_peak_threads,
            "peak_processes": self._session_peak_processes,
            "peak_tasks": self._session_peak_tasks,
        }
