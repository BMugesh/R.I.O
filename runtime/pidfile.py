"""PID and Single-Instance Management for R.I.O. Daemon.

Provides PID file persistence, active process verification,
duplicate-start protection, and stale PID detection on Windows and POSIX.
"""

import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("rio.runtime.pidfile")


def get_repo_root() -> Path:
    """Return repository root directory."""
    return Path(__file__).resolve().parent.parent


def get_data_dir() -> Path:
    """Return canonical data directory for R.I.O. runtime."""
    env_dir = os.getenv("RIO_DATA_DIR")
    if env_dir:
        d = Path(env_dir).resolve()
        d.mkdir(parents=True, exist_ok=True)
        return d
    d = get_repo_root() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


DEFAULT_PID_PATH = get_data_dir() / "rio.pid"


def is_process_active(pid: int) -> bool:
    """Check if a process with given PID is currently active in the operating system."""
    if not pid or pid <= 0:
        return False

    if sys.platform == "win32":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            SYNCHRONIZE = 0x00100000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE,
                False,
                pid,
            )
            if handle == 0:
                return False
            # Check exit code to be certain process hasn't terminated
            exit_code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            STILL_ACTIVE = 259
            is_active = (exit_code.value == STILL_ACTIVE)
            ctypes.windll.kernel32.CloseHandle(handle)
            return is_active
        except Exception as e:
            logger.debug(f"Error checking Windows PID {pid}: {e}")
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


class PIDManager:
    """Manages daemon process ID persistence and single-instance locks."""

    def __init__(self, pid_file: Optional[Path] = None):
        self.pid_file = pid_file or DEFAULT_PID_PATH
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)

    def read_pid(self) -> Optional[int]:
        """Read active PID from disk. Cleans up stale PID if process is dead."""
        if not self.pid_file.exists():
            return None

        try:
            raw = self.pid_file.read_text(encoding="utf-8").strip()
            if not raw:
                return None

            try:
                data = json.loads(raw)
                pid = int(data.get("pid"))
            except json.JSONDecodeError:
                pid = int(raw)

            if is_process_active(pid):
                return pid
            else:
                logger.warning(f"Detected stale PID {pid} in {self.pid_file}. Cleaning up.")
                self.remove_pid()
                return None
        except Exception as e:
            logger.warning(f"Failed to read PID from {self.pid_file}: {e}")
            return None

    def read_metadata(self) -> Dict[str, Any]:
        """Read daemon metadata associated with the PID file."""
        if not self.pid_file.exists():
            return {}

        try:
            raw = self.pid_file.read_text(encoding="utf-8").strip()
            data = json.loads(raw)
            pid = data.get("pid")
            if pid and is_process_active(int(pid)):
                return data
            elif pid:
                self.remove_pid()
                return {}
            return data
        except Exception:
            return {}

    def write_pid(self, pid: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Write current PID and metadata to file."""
        target_pid = pid or os.getpid()
        payload = {
            "pid": target_pid,
            "created_at": time.time(),
            "created_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "STANDBY",
            "mode": "local",
        }
        if metadata:
            payload.update(metadata)

        self.pid_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info(f"Registered daemon PID {target_pid} in {self.pid_file}")

    def remove_pid(self) -> bool:
        """Remove the PID file from disk."""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
                logger.info(f"Removed PID file: {self.pid_file}")
                return True
        except Exception as e:
            logger.warning(f"Failed to delete PID file {self.pid_file}: {e}")
        return False

    def is_running(self) -> bool:
        """Return True if daemon is currently running and active."""
        return self.read_pid() is not None
