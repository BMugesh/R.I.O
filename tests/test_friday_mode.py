"""Acceptance test suite for R.I.O. TRUE FRIDAY INTERACTION MODE.

Validates the silence-first architecture and anti-chatbot behavior:
- SpeechDecision gate: SILENT when conversation is naturally complete
- Dismissals ("Thanks.", "Okay.", "Got it.") produce SILENCE (zero Groq calls)
- Greetings ("Hey RIO.") produce concise acknowledgement ("Yes?")
- Polite commands ("Can you open Chrome?") are correctly dispatched to computer_agent,
  NEVER returning "I can't access" conversational refusals
- Instant Stop ("RIO, stop") halts and returns "Stopped."
- Standby ("RIO, standby") returns "Standing by."
- State machine supports LISTENING, MONITORING, WAITING, SPEAKING states
"""

import pytest
from apps.api.deps import Container
from packages.schemas.chat import ChatRequest
from runtime.state import RuntimeState, RuntimeStateMachine
from services.orchestrator.intent_engine import IntentCategory, IntentEngine
from services.orchestrator.speech_gate import SpeechDecision, SpeechGate


# ==============================================================================
# Test A: Silence on Idle / Dismissal Tokens (Rule: Silence is valid & preferred)
# ==============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("dismissal", [
    "Thanks.",
    "Thank you",
    "thank you so much",
    "Okay.",
    "ok",
    "Alright",
    "Got it.",
    "cool",
    "great",
    "good",
    "perfect",
    "nice",
    "That's all.",
    "No worries",
    "np",
])
async def test_dismissals_produce_silence(dismissal: str):
    """Conversation-ending utterances must produce empty response (SILENT) without calling Groq."""
    container = Container()
    # Mock should NOT be called if speech gate operates correctly
    mock_called = False

    async def tracking_generate(*args, **kwargs):
        nonlocal mock_called
        mock_called = True
        return {"content": "You're welcome!"}

    container.orchestrator.model_router.generate = tracking_generate
    container.orchestrator.response_engine.model_router.generate = tracking_generate

    req = ChatRequest(
        message=dismissal,
        sessionId="session_friday_silence",
        developerMode=False,
    )
    response = await container.orchestrator.process_chat(req)

    assert response.reply == ""
    assert response.status == "completed"
    assert not mock_called, f"Groq was called for dismissal '{dismissal}'!"


# ==============================================================================
# Test B: Greeting produces concise acknowledgement ("Yes?")
# ==============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("greeting", [
    "Hey RIO",
    "Hi RIO",
    "Hello",
    "hey",
])
async def test_greeting_produces_yes(greeting: str):
    """Greetings should receive a concise 'Yes?' acknowledgement without chatbot filler."""
    container = Container()
    container.model_router.default_provider = "mock"

    req = ChatRequest(
        message=greeting,
        sessionId="session_friday_greeting",
        developerMode=False,
    )
    response = await container.orchestrator.process_chat(req)

    assert response.reply.strip() == "Yes?"
    assert response.status == "completed"


# ==============================================================================
# Test C & E: Polite Commands are recognized as Tasks (Fix "I can't access")
# ==============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("polite_cmd", [
    "Can you open Chrome?",
    "Could you launch VS Code",
    "Please open Chrome",
    "Kindly open Spotify",
    "I want you to open VS Code",
    "Can you please take a screenshot",
])
async def test_polite_commands_classified_as_tasks(polite_cmd: str):
    """Polite phrasing must strip preambles and be classified as DEVICE_ACTION, NOT conversation."""
    intent_engine = IntentEngine()
    result = await intent_engine.classify_intent(polite_cmd)

    assert result["is_task"] is True, f"'{polite_cmd}' was not classified as a task!"
    assert result["category"] == IntentCategory.DEVICE_ACTION
    assert result["agent_id"] == "computer_agent"


@pytest.mark.asyncio
async def test_polite_command_execution_no_refusal():
    """'Can you open Chrome?' executes via computer_agent and never says 'I can't access'."""
    container = Container()
    container.model_router.default_provider = "mock"

    req = ChatRequest(
        message="Can you open Chrome?",
        sessionId="session_polite_exec",
        developerMode=True,
    )
    response = await container.orchestrator.process_chat(req)

    assert response.status == "completed"
    assert "cannot access" not in response.reply.lower()
    assert "can't access" not in response.reply.lower()
    assert "as an ai" not in response.reply.lower()
    assert response.developer_trace is not None
    assert len(response.developer_trace.steps) >= 1


# ==============================================================================
# Test D: Stop Command Halts Tasks
# ==============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("stop_cmd", [
    "RIO, stop",
    "stop",
    "halt",
    "cancel",
])
async def test_stop_command(stop_cmd: str):
    """'RIO, stop' must immediately respond with 'Stopped.' and cancel active tasks."""
    container = Container()

    req = ChatRequest(
        message=stop_cmd,
        sessionId="session_friday_stop",
        developerMode=False,
    )
    response = await container.orchestrator.process_chat(req)

    assert response.reply == "Stopped."
    assert response.status == "completed"


# ==============================================================================
# Test F: Standby Command
# ==============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("standby_cmd", [
    "RIO, standby",
    "standby",
    "stand by",
    "go to sleep",
])
async def test_standby_command(standby_cmd: str):
    """'RIO, standby' must immediately respond with 'Standing by.'."""
    container = Container()

    req = ChatRequest(
        message=standby_cmd,
        sessionId="session_friday_standby",
        developerMode=False,
    )
    response = await container.orchestrator.process_chat(req)

    assert response.reply == "Standing by."
    assert response.status == "completed"


# ==============================================================================
# Test G: SpeechGate Unit Evaluation
# ==============================================================================
def test_speech_gate_decisions():
    """Test SpeechGate.evaluate() under different scenarios."""
    # Dismissals -> SILENT
    assert SpeechGate.evaluate("Thanks") == SpeechDecision.SILENT
    assert SpeechGate.evaluate("Thank you so much!") == SpeechDecision.SILENT
    assert SpeechGate.evaluate("Okay") == SpeechDecision.SILENT
    assert SpeechGate.evaluate("All right.") == SpeechDecision.SILENT
    assert SpeechGate.evaluate("Got it") == SpeechDecision.SILENT
    assert SpeechGate.evaluate("That's all") == SpeechDecision.SILENT
    assert SpeechGate.evaluate("I'm good, thanks") == SpeechDecision.SILENT

    # Empty / whitespace -> SILENT
    assert SpeechGate.evaluate("") == SpeechDecision.SILENT
    assert SpeechGate.evaluate("   ") == SpeechDecision.SILENT

    # Greetings -> ACKNOWLEDGE
    assert SpeechGate.evaluate("Hey RIO") == SpeechDecision.ACKNOWLEDGE
    assert SpeechGate.evaluate("Hello") == SpeechDecision.ACKNOWLEDGE

    # System commands -> ACKNOWLEDGE
    assert SpeechGate.evaluate("RIO, stop") == SpeechDecision.ACKNOWLEDGE
    assert SpeechGate.evaluate("Standby") == SpeechDecision.ACKNOWLEDGE

    # Task completed -> ACKNOWLEDGE
    assert SpeechGate.evaluate("Open Chrome", task_status="completed") == SpeechDecision.ACKNOWLEDGE

    # Task failed -> ERROR
    assert SpeechGate.evaluate("Open Chrome", task_status="failed") == SpeechDecision.ERROR

    # Questions -> RESPOND
    assert SpeechGate.evaluate("What is the speed of light?") == SpeechDecision.RESPOND
    assert SpeechGate.evaluate("How does backpropagation work?") == SpeechDecision.RESPOND
    assert SpeechGate.evaluate("Why is the sky blue?") == SpeechDecision.RESPOND


# ==============================================================================
# Test H: State Machine New States
# ==============================================================================
def test_runtime_state_machine_new_states():
    """Verify state machine transitions to LISTENING, MONITORING, WAITING, SPEAKING."""
    sm = RuntimeStateMachine(initial_state=RuntimeState.STANDBY)

    assert sm.transition_to(RuntimeState.LISTENING)
    assert sm.current_state == RuntimeState.LISTENING

    assert sm.transition_to(RuntimeState.PROCESSING)
    assert sm.current_state == RuntimeState.PROCESSING

    assert sm.transition_to(RuntimeState.EXECUTING)
    assert sm.current_state == RuntimeState.EXECUTING

    assert sm.transition_to(RuntimeState.MONITORING)
    assert sm.current_state == RuntimeState.MONITORING

    assert sm.transition_to(RuntimeState.WAITING)
    assert sm.current_state == RuntimeState.WAITING

    assert sm.transition_to(RuntimeState.SPEAKING)
    assert sm.current_state == RuntimeState.SPEAKING

    assert sm.transition_to(RuntimeState.ACTIVE)
    assert sm.current_state == RuntimeState.ACTIVE
