"""Unit tests for R.I.O. universal schemas."""
import pytest
pytestmark = pytest.mark.unit



import pytest
from packages.schemas import (
    RIOInput,
    InputType,
    RIOEvent,
    EventType,
    AgentManifest,
    AgentRiskLevel,
    Task,
    TaskPlan,
    TaskStep,
    Action,
    Evidence,
    VerificationStrategy,
    ToolDefinition,
    ToolCall,
    ApprovalRequest,
    ApprovalStatus,
    MemoryItem,
    MemoryType,
    QuantumJob,
    QuantumAlgorithmType,
)


def test_universal_input_normalization():
    inp = RIOInput(type=InputType.TEXT, payload="Hi RIO")
    assert inp.type == InputType.TEXT
    assert inp.get_text_content() == "Hi RIO"

    inp_dict = RIOInput(type=InputType.TEXT, payload={"text": "Hello"})
    assert inp_dict.get_text_content() == "Hello"


def test_internal_event_envelope():
    ev = RIOEvent(type=EventType.TASK_CREATED, task_id="task_123", payload={"goal": "Search web"})
    assert ev.type == EventType.TASK_CREATED
    assert ev.task_id == "task_123"
    assert ev.payload["goal"] == "Search web"


def test_task_dag_and_verification_strategy():
    step = TaskStep(
        name="Open WhatsApp",
        agent_id="computer_agent",
        action=Action(action_type="open_application", target="whatsapp"),
        verification_strategy=VerificationStrategy(
            strategy_type="device_observation",
            expected_state={"window_open": True},
        ),
    )
    plan = TaskPlan(goal="Send message", steps=[step])
    task = Task(goal="Send message", plan=plan)

    assert len(task.plan.steps) == 1
    assert task.plan.steps[0].verification_strategy.strategy_type == "device_observation"


def test_quantum_job_schema():
    job = QuantumJob(algorithm=QuantumAlgorithmType.QAOA, problem_matrix=[[0, 1], [1, 0]])
    assert job.algorithm == QuantumAlgorithmType.QAOA
    assert job.status == "pending"
