"""Unit tests for R.I.O. Runtime Shutdown Handler."""

import asyncio
import pytest
from runtime.pidfile import PIDManager
from runtime.shutdown import RuntimeShutdownHandler
from runtime.state import RuntimeState, RuntimeStateMachine

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_graceful_shutdown_hooks(tmp_path):
    """Verify shutdown handler runs registered hooks in reverse order."""
    pid_file = tmp_path / "shutdown_test.pid"
    pm = PIDManager(pid_file=pid_file)
    sm = RuntimeStateMachine(initial_state=RuntimeState.ACTIVE, state_file=tmp_path / "state.json")
    handler = RuntimeShutdownHandler(state_machine=sm, pid_manager=pm)

    pm.write_pid(12345)
    execution_order = []

    def hook1():
        execution_order.append("hook1")

    async def hook2():
        execution_order.append("hook2")

    handler.register_cleanup_hook(hook1)
    handler.register_cleanup_hook(hook2)

    assert handler.is_shutting_down is False
    handler.request_shutdown("Testing shutdown")
    assert handler.is_shutting_down is True

    await handler.execute_shutdown()

    # Verify hooks executed in LIFO order
    assert execution_order == ["hook2", "hook1"]
    assert sm.current_state == RuntimeState.STOPPED
    assert not pid_file.exists()
