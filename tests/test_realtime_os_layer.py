"""Comprehensive End-to-End Acceptance Test Suite for R.I.O. Real-Time OS Layer.

Covers:
- Scenario 1 (Rule 43): Conversation & Standby Lifecycle
- Scenario 2 (Rule 43): Goal Execution ("Prepare my coding environment for RIO")
- Scenario 3 (Rule 43): Real Host Telemetry (No Remote LLM)
- Scenario 4 (Rule 43): Autonomous Multi-Step Task with Evidence Verification
- Scenario 5 (Rule 43): Event-Driven Proactive Assistance (Process Exit, Battery, Downloads)
- Scenario 6 (Rule 43): Multi-Turn Follow-Up Context Continuity
- Rule 44: Offline Mode (Local Capabilities Continue Working When Offline)
- Rule 45: Remote Groq Failure Graceful Fallback (Honest Operational Response)
"""

import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import time
from unittest.mock import AsyncMock, patch

import pytest

from agents.computer.agent import ComputerAgent
from agents.filesystem.agent import FileSystemAgent
from agents.system.agent import LocalSystemAgent
from agents.verification.agent import VerificationAgent
from apps.api.deps import Container
from packages.schemas.chat import ChatRequest
from packages.schemas.input import InputType, RIOInput
from packages.schemas.tasks import TaskStatus
from runtime.event_listener import EventListener, RuntimeEvent
from services.conversation.context import ConversationContext
from services.conversation.intent import IntentType
from services.conversation.manager import ConversationManager
from services.model_router.router import ModelRouter, RouteStrategy
from services.observability.proactive_monitor import ProactiveMonitor, ProactiveSuggestion
from runtime.state import RuntimeState


# ==============================================================================
# Scenario 1 — Conversation & Standby Lifecycle (Rule 43)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_1_conversation_and_standby():
    """Verify voice dialogue transitions between STANDBY and ACTIVE cleanly."""
    container = Container()
    voice_mgr = container.voice_runtime_manager
    conv_mgr = container.conversation_manager

    # Initially in STANDBY mode
    voice_mgr.state_machine.transition_to(RuntimeState.STANDBY)
    assert voice_mgr.is_standby is True

    # User wakes assistant: "Hey RIO, are you there?"
    voice_mgr.state_machine.transition_to(RuntimeState.ACTIVE)
    assert voice_mgr.is_active is True

    # Conversational utterance handled in ACTIVE state
    intent, reply = await conv_mgr.handle_user_utterance("Hey RIO, are you there?")
    assert intent in (IntentType.CONVERSATIONAL, IntentType.ACTION)
    assert len(reply) > 0

    # User says: "Stand by."
    intent_standby, reply_standby = await conv_mgr.handle_user_utterance("Stand by.")
    assert intent_standby == IntentType.SYSTEM_STANDBY
    assert "standing by" in reply_standby.lower()

    voice_mgr.state_machine.transition_to(RuntimeState.STANDBY)
    assert voice_mgr.is_standby is True


# ==============================================================================
# Scenario 2 — Goal Execution: "Prepare my coding environment for RIO" (Rule 43)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_2_goal_execution_coding_environment():
    """Verify multi-step goal decomposition, real execution, and evidence verification."""
    container = Container()
    container.model_router.default_provider = "mock"

    req = ChatRequest(
        message="Prepare my coding environment for RIO",
        sessionId="session_scenario_02",
        developerMode=True,
    )
    response = await container.orchestrator.process_chat(req)

    assert response.status == "completed"
    assert response.developer_trace is not None
    assert len(response.developer_trace.steps) == 4

    step_names = [s.name for s in response.developer_trace.steps]
    assert any("Inspect Host" in name for name in step_names)
    assert any("VS Code" in name for name in step_names)
    assert any("Repository" in name for name in step_names)
    assert any("Readiness" in name for name in step_names)

    # Every step must have real verified evidence
    for step in response.developer_trace.steps:
        assert step.evidence is not None
        assert len(step.evidence) > 0
        assert any(e.verified for e in step.evidence)


# ==============================================================================
# Scenario 3 — Real Telemetry Query (No Remote LLM) (Rule 43)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_3_real_telemetry_no_remote_llm():
    """Verify physical hardware telemetry is retrieved locally without Groq."""
    router = ModelRouter()
    query = "What is my battery level and how much RAM is free?"

    # Strategy must be NO_AI_REQUIRED
    strategy = router.determine_route_strategy(query, task_type="conversation")
    assert strategy == RouteStrategy.NO_AI_REQUIRED

    # LocalSystemAgent executes physically on host
    sys_agent = LocalSystemAgent()
    result = await sys_agent.run(RIOInput(type=InputType.TEXT, payload={"query": query}), context={})

    assert result.status.value == "success"
    assert "RAM" in result.message or "Memory" in result.message or "Battery" in result.message
    assert len(result.evidence) > 0
    assert result.evidence[0].verified is True


# ==============================================================================
# Scenario 4 — Autonomous Multi-Step Task with Real Evidence Verification (Rule 43)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_4_autonomous_multistep_task_with_real_verification():
    """Verify multi-step execution with genuine filesystem and window verification."""
    container = Container()
    container.model_router.default_provider = "mock"

    req = ChatRequest(
        message="Take a screenshot",
        sessionId="session_scenario_04",
        developerMode=True,
    )
    response = await container.orchestrator.process_chat(req)

    assert response.status == "completed"
    assert response.developer_trace is not None
    assert len(response.developer_trace.steps) == 2

    # Step 1: screen capture
    step1 = response.developer_trace.steps[0]
    assert step1.evidence[0].verified is True
    # Step 2: verified file on disk
    step2 = response.developer_trace.steps[1]
    assert step2.evidence[0].verified is True
    assert step2.evidence[0].type == "file_check"


# ==============================================================================
# Scenario 5 — Event-Driven Proactive Assistance (Rule 43, 34, 35)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_5_event_driven_proactive_assistance():
    """Verify deterministic background event triggers without continuous remote LLM polling."""
    bus = EventListener()
    emitted_events = []
    bus.subscribe_all(lambda ev: emitted_events.append(ev))

    monitor = ProactiveMonitor(event_listener=bus, check_interval=0.1)

    # 1. Process termination detection
    fake_pid = 99999999  # Guaranteed non-existent PID
    monitor.watch_process(fake_pid, label="Background Test Build")

    suggestions = await monitor.tick()
    assert len(suggestions) >= 1
    build_sug = next((s for s in suggestions if s.event_type == "proactive.process_exit"), None)
    assert build_sug is not None
    assert "Background Test Build" in build_sug.message
    assert any(e.type == "proactive.process_exit" for e in emitted_events)

    # 2. Watched download completion detection
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        tmp.write(b"0" * 1024)
        tmp_path = tmp.name

    try:
        monitor.watch_file(tmp_path, label="Model weights", target_size=1024)
        dl_suggestions = await monitor.tick()
        assert len(dl_suggestions) >= 1
        dl_sug = next((s for s in dl_suggestions if s.event_type == "proactive.download_completed"), None)
        assert dl_sug is not None
        assert "Model weights" in dl_sug.message
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ==============================================================================
# Scenario 6 — Multi-Turn Follow-Up Context Continuity (Rule 43)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_6_followup_context():
    """Verify that conversation context tracks targets across multi-turn interactions."""
    ctx = ConversationContext()

    # Turn 1: User asks to open Chrome
    ctx.record_action("open", "Chrome", details={"source": "user_command"})
    assert ctx.current_application == "Chrome"
    assert ctx.get_entity("it") == "Chrome"
    assert ctx.get_entity("target") == "Chrome"

    # Turn 2: User says "Search for Python release notes"
    # Follow-up resolution can resolve target application and context
    assert len(ctx.recent_actions) == 1
    assert ctx.recent_actions[0]["target"] == "Chrome"

    # Turn 3: Set workspace memory
    ctx.set_workspace("c:/Mugi/Projects/RIO", git_branch="main")
    assert ctx.workspace_context["path"] == "c:/Mugi/Projects/RIO"
    assert ctx.workspace_context["git_branch"] == "main"
    assert ctx.get_entity("workspace") == "c:/Mugi/Projects/RIO"


# ==============================================================================
# Rule 44 — Offline Test
# ==============================================================================
@pytest.mark.asyncio
async def test_rule_44_offline_mode():
    """Verify that all local OS, hardware, file, and control capabilities work offline."""
    # 1. Local telemetry works offline
    sys_agent = LocalSystemAgent()
    sys_res = await sys_agent.run(RIOInput(type=InputType.TEXT, payload={"query": "cpu"}), context={})
    assert sys_res.status.value == "success"
    assert "cpu" in sys_res.message.lower()

    # 2. Local filesystem operations work offline
    fs_agent = FileSystemAgent()
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"offline test data")
        tmp_file = tmp.name

    try:
        fs_res = await fs_agent.run(
            RIOInput(type=InputType.TEXT, payload={"action": "read_file", "path": tmp_file}),
            context={},
        )
        assert fs_res.status.value == "success"
        assert "offline test data" in fs_res.data.get("content", "")
    finally:
        if os.path.exists(tmp_file):
            os.remove(tmp_file)

    # 3. Local verification works offline
    verif_agent = VerificationAgent()
    v_res = await verif_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action_type": "verify_file", "file_path": __file__}),
        context={},
    )
    assert v_res.status.value == "success"
    assert v_res.data.get("verified") is True


# ==============================================================================
# Rule 45 — Groq Failure / Rate Limit Graceful Fallback
# ==============================================================================
@pytest.mark.asyncio
async def test_rule_45_groq_failure_graceful_handling():
    """Verify that remote LLM failure returns an honest operational response without crashing."""
    container = Container()

    # Force model router to simulate remote API failure
    async def mock_failing_generate(*args, **kwargs):
        raise ConnectionError("Groq API rate limit exceeded (HTTP 429) or offline")

    container.orchestrator.response_engine.model_router.generate = mock_failing_generate

    req = ChatRequest(
        message="What is the meaning of life?",
        sessionId="session_fail_01",
        developerMode=False,
    )
    response = await container.orchestrator.process_chat(req)

    # Must return completed status with honest local fallback notice, not crash or fake chatbot cheer
    assert response.status == "completed"
    assert "local fallback mode" in response.reply.lower()
    assert "monitoring" in response.reply.lower() or "active" in response.reply.lower()
