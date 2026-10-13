"""Unit tests for R.I.O. Runtime Singleton & Multi-Instance Guards."""

import os
import pytest
from runtime.pidfile import PIDManager, is_process_active

pytestmark = pytest.mark.unit


def test_is_process_active():
    """Verify is_process_active correctly identifies running vs dead PIDs."""
    assert is_process_active(os.getpid()) is True
    assert is_process_active(-1) is False
    assert is_process_active(0) is False
    assert is_process_active(999999) is False


def test_singleton_lock_contention(tmp_path):
    """Verify two managers pointing to the same file enforce singleton."""
    pid_file = tmp_path / "singleton.pid"
    mgr1 = PIDManager(pid_file=pid_file)
    mgr2 = PIDManager(pid_file=pid_file)

    assert mgr1.is_running() is False
    assert mgr2.is_running() is False

    mgr1.write_pid(os.getpid())
    assert mgr1.is_running() is True
    assert mgr2.is_running() is True
    assert mgr2.read_pid() == os.getpid()

    mgr1.remove_pid()
    assert mgr2.is_running() is False
