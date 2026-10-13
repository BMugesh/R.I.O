"""Subprocess Ownership and Lifecycle Tracker (Milestone 4.5).

Tracks child processes explicitly spawned by tests (Chrome, Node, Python workers)
using parent PID hierarchy and explicit handles. Never blindly kills unrelated processes.
"""

import logging
import os
import subprocess
from typing import Any, List, Optional, Set, Union
import psutil

logger = logging.getLogger("rio.test_governor.process")


class ProcessTracker:
    """Tracks and guarantees teardown of test-owned subprocesses."""

    def __init__(self):
        self._current_proc = psutil.Process(os.getpid())
        self._registered_handles: Set[Any] = set()
        self._baseline_child_pids: Set[int] = set()

    def capture_baseline(self) -> None:
        """Record currently alive child PIDs before a test begins."""
        self._baseline_child_pids = set(self.get_child_pids())

    def register_process(self, proc: Union[subprocess.Popen, psutil.Process, int]) -> None:
        """Explicitly register a test-spawned process for lifecycle management."""
        self._registered_handles.add(proc)

    def get_child_pids(self) -> List[int]:
        """Return list of alive child process PIDs owned by current process."""
        try:
            children = self._current_proc.children(recursive=True)
            return [c.pid for c in children if c.is_running()]
        except Exception:
            return []

    def get_new_child_processes(self) -> List[psutil.Process]:
        """Return list of child processes spawned since baseline."""
        try:
            children = self._current_proc.children(recursive=True)
            return [c for c in children if c.pid not in self._baseline_child_pids and c.is_running()]
        except Exception:
            return []

    def cleanup_owned_processes(self, timeout: float = 1.0) -> List[int]:
        """Terminate and reap all newly created or registered child processes.
        Returns list of terminated PIDs.
        """
        terminated_pids: List[int] = []
        procs_to_terminate: List[psutil.Process] = []

        # 1. Inspect registered handles
        for item in list(self._registered_handles):
            try:
                if isinstance(item, subprocess.Popen):
                    if item.poll() is None:
                        try:
                            item.terminate()
                            item.wait(timeout=timeout)
                        except Exception:
                            item.kill()
                            item.wait(timeout=0.2)
                        terminated_pids.append(item.pid)
                elif isinstance(item, psutil.Process):
                    if item.is_running():
                        item.terminate()
                        procs_to_terminate.append(item)
                        terminated_pids.append(item.pid)
                elif isinstance(item, int):
                    if psutil.pid_exists(item):
                        p = psutil.Process(item)
                        p.terminate()
                        procs_to_terminate.append(p)
                        terminated_pids.append(item)
            except Exception as e:
                logger.debug(f"Note terminating handle: {e}")

        self._registered_handles.clear()

        # 2. Inspect children spawned since baseline
        new_children = self.get_new_child_processes()
        for child in new_children:
            if child.pid not in terminated_pids:
                try:
                    child.terminate()
                    procs_to_terminate.append(child)
                    terminated_pids.append(child.pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

        # 3. Wait for graceful exit
        if procs_to_terminate:
            _, alive = psutil.wait_procs(procs_to_terminate, timeout=timeout)
            # Force kill any stubborn remnants
            for stubborn in alive:
                try:
                    logger.warning(f"Force killing persistent child process PID {stubborn.pid}")
                    stubborn.kill()
                except Exception:
                    pass

        return terminated_pids
