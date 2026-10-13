"""Unit and Integration Tests for R.I.O. Runtime Lifecycle (Milestone 5.x)."""

import os
from pathlib import Path
import time
import pytest

from runtime.lifecycle import RuntimeLifecycle
from runtime.pidfile import PIDManager
from runtime.state import RuntimeState, RuntimeStateMachine

pytestmark = pytest.mark.unit


def test_pid_manager_lifecycle(tmp_path):
    """Verify PID writing, active checking, and cleanup."""
    test_pid_file = tmp_path / "test_rio.pid"
    pm = PIDManager(pid_file=test_pid_file)

    assert pm.is_running() is False
    assert pm.read_pid() is None

    # Write current active PID
    current_pid = os.getpid()
    pm.write_pid(current_pid, metadata={"status": "STANDBY", "mode": "voice"})

    assert pm.is_running() is True
    assert pm.read_pid() == current_pid
    metadata = pm.read_metadata()
    assert metadata["status"] == "STANDBY"
    assert metadata["mode"] == "voice"

    # Remove PID
    pm.remove_pid()
    assert pm.is_running() is False
    assert pm.read_pid() is None


def test_stale_pid_auto_cleanup(tmp_path):
    """Verify stale PID from dead process is automatically detected and purged."""
    test_pid_file = tmp_path / "stale_rio.pid"
    pm = PIDManager(pid_file=test_pid_file)

    # Inactive PID (e.g. 999999)
    inactive_pid = 999999
    pm.write_pid(inactive_pid, metadata={"status": "STANDBY"})

    # read_pid should detect stale PID and unlink
    assert pm.read_pid() is None
    assert pm.is_running() is False
    assert not test_pid_file.exists()


def test_runtime_lifecycle_duplicate_protection(tmp_path):
    """Verify duplicate startup rejection when PID is already active."""
    test_pid_file = tmp_path / "rio_dup.pid"
    pm = PIDManager(pid_file=test_pid_file)
    pm.write_pid(os.getpid(), metadata={"status": "STANDBY"})

    lc = RuntimeLifecycle(pid_manager=pm)
    res = lc.start_daemon(detached=False)

    assert res["success"] is False
    assert res["already_running"] is True
    assert res["pid"] == os.getpid()
    assert "already running" in res["message"].lower()

    pm.remove_pid()


def test_runtime_status_reporting(tmp_path):
    """Verify get_status returns accurate fields."""
    test_pid_file = tmp_path / "rio_status.pid"
    pm = PIDManager(pid_file=test_pid_file)
    pm.write_pid(os.getpid(), metadata={"status": "STANDBY", "mode": "local"})

    lc = RuntimeLifecycle(pid_manager=pm)
    st = lc.get_status()

    assert st["running"] is True
    assert st["pid"] == os.getpid()
    assert st["mode"] == "STANDBY"
    assert st["llm"] == "GROQ"
    assert st["stt"] == "GROQ WHISPER"
    assert st["tts"] in ("FEMALE", "MOCK")

    pm.remove_pid()
