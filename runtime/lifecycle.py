"""Runtime Process Lifecycle Controller for R.I.O. (Milestone 5.x).

Manages detached daemon spawning, single-instance verification,
graceful shutdown signals, status inspection, and restart flows.
"""

import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, Optional

from runtime.pidfile import PIDManager, get_data_dir, get_repo_root, is_process_active
from runtime.state import RuntimeState, RuntimeStateMachine

logger = logging.getLogger("rio.runtime.lifecycle")


class RuntimeLifecycle:
    """Controls daemon startup, status query, and shutdown from CLI or scripts."""

    def __init__(self, pid_manager: Optional[PIDManager] = None):
        self.pid_manager = pid_manager or PIDManager()

    def is_running(self) -> bool:
        return self.pid_manager.is_running()

    def get_pid(self) -> Optional[int]:
        return self.pid_manager.read_pid()

    def start_daemon(
        self,
        detached: bool = True,
        mode: str = "voice",
        log_to_file: bool = True,
    ) -> Dict[str, Any]:
        """Start the persistent R.I.O. background daemon."""
        active_pid = self.pid_manager.read_pid()
        if active_pid:
            metadata = self.pid_manager.read_metadata()
            state = metadata.get("status", "STANDBY")
            return {
                "success": False,
                "already_running": True,
                "pid": active_pid,
                "status": state,
                "message": f"R.I.O. is already running.\nPID: {active_pid}\nStatus: {state}",
            }

        # Resolve python executable and paths
        repo_root = get_repo_root()
        python_exe = sys.executable
        cwd = str(repo_root)

        cmd = [python_exe, "-m", "runtime.daemon", "--mode", mode]

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["RIO_LOCAL_RUNTIME"] = "1"
        env["PYTHONPATH"] = f"{repo_root};{env.get('PYTHONPATH', '')}"

        creation_flags = 0
        if sys.platform == "win32":
            CREATE_NO_WINDOW = 0x08000000
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            creation_flags = CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

        log_dir = get_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        runtime_log_path = log_dir / "runtime.log"

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=env,
                creationflags=creation_flags,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=(sys.platform != "win32"),
            )

            # Wait briefly for PID registration
            deadline = time.time() + 4.0
            spawned_pid = proc.pid
            started = False
            while time.time() < deadline:
                exit_code = proc.poll()
                if exit_code is not None:
                    err_hint = ""
                    try:
                        if runtime_log_path.exists():
                            lines = runtime_log_path.read_text(encoding="utf-8").strip().splitlines()
                            if lines:
                                err_hint = lines[-1]
                    except Exception:
                        pass
                    msg = f"Daemon process exited prematurely with code {exit_code}."
                    if err_hint:
                        msg += f" Error: {err_hint}"
                    logger.error(msg)
                    return {
                        "success": False,
                        "already_running": False,
                        "pid": None,
                        "status": "ERROR",
                        "message": msg,
                    }

                current_pid = self.pid_manager.read_pid()
                if current_pid:
                    spawned_pid = current_pid
                    started = True
                    break
                time.sleep(0.1)

            if not started:
                exit_code = proc.poll()
                if exit_code is not None:
                    return {
                        "success": False,
                        "already_running": False,
                        "pid": None,
                        "status": "ERROR",
                        "message": f"Daemon exited with code {exit_code}.",
                    }
                if is_process_active(spawned_pid):
                    self.pid_manager.write_pid(spawned_pid, metadata={"status": "STANDBY", "mode": mode})
                    started = True
                else:
                    return {
                        "success": False,
                        "already_running": False,
                        "pid": None,
                        "status": "ERROR",
                        "message": "Daemon failed to remain active after launch.",
                    }

            return {
                "success": True,
                "already_running": False,
                "pid": spawned_pid,
                "status": "STANDBY",
                "message": "R.I.O. background runtime started successfully.",
            }

        except Exception as e:
            logger.error(f"Failed to launch R.I.O. background daemon: {e}")
            return {
                "success": False,
                "already_running": False,
                "pid": None,
                "status": "ERROR",
                "message": str(e),
            }

    def stop_daemon(self, timeout: float = 5.0) -> Dict[str, Any]:
        """Signal and stop the active R.I.O. daemon."""
        pid = self.pid_manager.read_pid()
        if not pid:
            return {
                "success": True,
                "was_running": False,
                "message": "R.I.O. is not currently running.",
            }

        # Signal shutdown via shutdown trigger file or process signal
        shutdown_flag = get_data_dir() / "runtime_shutdown.flag"
        try:
            shutdown_flag.parent.mkdir(parents=True, exist_ok=True)
            shutdown_flag.write_text("shutdown", encoding="utf-8")
        except Exception:
            pass

        # Wait for graceful termination
        deadline = time.time() + timeout
        stopped = False
        while time.time() < deadline:
            if not is_process_active(pid):
                stopped = True
                break
            time.sleep(0.2)

        # Force terminate if still alive
        if not stopped and is_process_active(pid):
            if sys.platform == "win32":
                try:
                    import ctypes
                    PROCESS_TERMINATE = 1
                    h = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
                    if h:
                        ctypes.windll.kernel32.TerminateProcess(h, 0)
                        ctypes.windll.kernel32.CloseHandle(h)
                except Exception:
                    pass
            else:
                try:
                    import signal
                    os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass

        self.pid_manager.remove_pid()
        try:
            if shutdown_flag.exists():
                shutdown_flag.unlink()
        except Exception:
            pass

        # Update persisted state
        sm = RuntimeStateMachine()
        sm.transition_to(RuntimeState.STOPPED)

        return {
            "success": True,
            "was_running": True,
            "pid": pid,
            "message": f"R.I.O. daemon (PID {pid}) stopped cleanly.",
        }

    def restart_daemon(self) -> Dict[str, Any]:
        """Stop and restart daemon."""
        self.stop_daemon()
        time.sleep(1.0)
        return self.start_daemon()

    def get_status(self) -> Dict[str, Any]:
        """Fetch comprehensive status information for CLI display."""
        pid = self.pid_manager.read_pid()
        is_running = (pid is not None)
        persisted_state = RuntimeStateMachine.read_persisted_state()
        metadata = self.pid_manager.read_metadata()

        mode = metadata.get("status", "STANDBY") if is_running else "STOPPED"
        start_time = metadata.get("created_at")
        uptime_str = "0s"
        if start_time and is_running:
            uptime_sec = int(time.time() - float(start_time))
            hours, remainder = divmod(uptime_sec, 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_str = f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s"

        wake_phrase = os.getenv("RIO_WAKE_PHRASE", "Hey RIO")
        voice = os.getenv("RIO_VOICE", "female").upper()

        return {
            "running": is_running,
            "pid": pid,
            "mode": mode,
            "status": "RUNNING" if is_running else "STOPPED",
            "voice": "READY" if is_running else "OFFLINE",
            "voice_gender": voice,
            "wake_phrase": wake_phrase,
            "llm": "GROQ",
            "stt": "GROQ WHISPER",
            "tts": voice,
            "current_task": persisted_state.get("active_task") or "IDLE",
            "uptime": uptime_str,
        }
