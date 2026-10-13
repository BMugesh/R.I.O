"""Unit tests for R.I.O. M5.5 Adaptive Verification."""

import pytest
pytestmark = [pytest.mark.unit]

from packages.schemas.agents import Action, Evidence
from packages.schemas.tasks import TaskStep, VerificationStrategy
from services.verification.adaptive import AdaptiveVerifier, VerificationLevel
from services.verification.engine import VerificationEngine


def test_verification_level_none():
    step = TaskStep(id="s1", name="Chat", agent_id="conversation_agent", action=Action(action_type="chat"))
    res = AdaptiveVerifier.evaluate(step, level=VerificationLevel.NONE)
    assert res.status == "verified"
    assert res.confidence == 1.0


def test_verification_level_basic():
    step = TaskStep(id="s1", name="App Launch", agent_id="computer_agent", action=Action(action_type="open"))

    # Passes with positive observation
    res_pass = AdaptiveVerifier.evaluate(step, observation={"success": True}, level=VerificationLevel.BASIC)
    assert res_pass.status == "verified"

    # Fails when observation is empty and no evidence
    res_fail = AdaptiveVerifier.evaluate(step, observation={}, evidence_list=[], level=VerificationLevel.BASIC)
    assert res_fail.status == "failed"


def test_verification_level_strict():
    step = TaskStep(
        id="s1",
        name="Write File",
        agent_id="filesystem_agent",
        action=Action(action_type="write_file"),
        verification_strategy=VerificationStrategy(strategy_type="file_check", expected_state={"file_path": "report.pdf"}),
    )

    # 1. File exists but size is 0 bytes -> inconclusive for strict
    ev_zero = Evidence(type="file_check", source="fs", data={"path": "report.pdf", "size_bytes": 0}, verified=True, confidence=0.95)
    res_inconc = AdaptiveVerifier.evaluate(step, evidence_list=[ev_zero], level=VerificationLevel.STRICT)
    assert res_inconc.status == "inconclusive"

    # 2. File exists and size > 0 -> verified for strict
    ev_valid = Evidence(type="file_check", source="fs", data={"path": "report.pdf", "size_bytes": 1024}, verified=True, confidence=0.95)
    res_verified = AdaptiveVerifier.evaluate(step, evidence_list=[ev_valid], level=VerificationLevel.STRICT)
    assert res_verified.status == "verified"


def test_verification_level_critical():
    step = TaskStep(
        id="s1",
        name="Delete Database",
        agent_id="computer_agent",
        action=Action(action_type="delete"),
    )

    ev1 = Evidence(type="api_status", source="http", verified=True, confidence=0.95)
    ev2 = Evidence(type="file_check", source="fs", verified=True, confidence=0.95)

    # 1 evidence -> inconclusive (must have 2+)
    res_single = AdaptiveVerifier.evaluate(step, evidence_list=[ev1], level=VerificationLevel.CRITICAL)
    assert res_single.status == "inconclusive"

    # 2 independent evidences -> verified
    res_dual = AdaptiveVerifier.evaluate(step, evidence_list=[ev1, ev2], level=VerificationLevel.CRITICAL)
    assert res_dual.status == "verified"
    assert res_dual.confidence >= 0.95


@pytest.mark.asyncio
async def test_verification_engine_backward_compatibility():
    engine = VerificationEngine()
    step = TaskStep(
        id="s1",
        name="Test",
        agent_id="research_agent",
        action=Action(action_type="search"),
        verification_strategy=VerificationStrategy(strategy_type="assertion", expected_state={"verified": True}),
    )
    ev = Evidence(type="assertion", source="test", data={"verified": True}, verified=True, confidence=1.0)

    # verify_step returns bool
    is_ok = await engine.verify_step(step, evidence_list=[ev])
    assert is_ok is True

    # verify_step_adaptive returns VerificationResult
    res = await engine.verify_step_adaptive(step, evidence_list=[ev])
    assert res.status == "verified"
