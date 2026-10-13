"""Unit tests for Runtime and Voice State Machine (Milestone 5.x)."""

import pytest
from runtime.state import RuntimeState, RuntimeStateMachine

pytestmark = pytest.mark.unit


def test_runtime_state_machine_transitions(tmp_path):
    """Verify full state machine progression and persistence."""
    state_file = tmp_path / "runtime_state.json"
    sm = RuntimeStateMachine(initial_state=RuntimeState.STOPPED, state_file=state_file)

    history = []
    sm.register_listener(lambda old, new: history.append((old, new)))

    # Startup sequence
    sm.transition_to(RuntimeState.STARTING)
    assert sm.current_state == RuntimeState.STARTING

    sm.transition_to(RuntimeState.STANDBY)
    assert sm.current_state == RuntimeState.STANDBY

    # Wake sequence
    sm.transition_to(RuntimeState.AWAKING)
    sm.transition_to(RuntimeState.ACTIVE)
    assert sm.current_state == RuntimeState.ACTIVE

    # Command execution
    sm.transition_to(RuntimeState.PROCESSING, task_info="Open Chrome")
    sm.transition_to(RuntimeState.EXECUTING)
    sm.transition_to(RuntimeState.VERIFYING)
    sm.transition_to(RuntimeState.RESPONDING)

    # Crucial M5.x requirement: Remain ACTIVE after response!
    sm.transition_to(RuntimeState.ACTIVE)
    assert sm.current_state == RuntimeState.ACTIVE

    # User says "RIO, standby"
    sm.transition_to(RuntimeState.STANDBY)
    assert sm.current_state == RuntimeState.STANDBY

    # Verify history
    assert len(history) == 10
    assert history[0] == (RuntimeState.STOPPED, RuntimeState.STARTING)
    assert history[1] == (RuntimeState.STARTING, RuntimeState.STANDBY)
    assert history[-1] == (RuntimeState.ACTIVE, RuntimeState.STANDBY)

    # Verify persisted state
    saved = RuntimeStateMachine.read_persisted_state(state_file)
    assert saved["state"] == RuntimeState.STANDBY.value
