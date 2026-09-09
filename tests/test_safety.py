"""Unit tests for Safety and Approval subsystem."""

import pytest
from packages.schemas.agents import AgentRiskLevel
from packages.schemas.safety import ApprovalDecision, ApprovalStatus
from services.safety.approval_engine import ApprovalEngine
from services.safety.policy_engine import PolicyEngine
from services.safety.sanitizer import Sanitizer


def test_policy_risk_classification():
    policy = PolicyEngine()
    assert policy.evaluate_action_risk("search_web") == AgentRiskLevel.LOW
    assert policy.evaluate_action_risk("screenshot") == AgentRiskLevel.LOW
    assert policy.evaluate_action_risk("send_message") == AgentRiskLevel.MEDIUM
    assert policy.evaluate_action_risk("delete_file") == AgentRiskLevel.HIGH
    assert policy.evaluate_action_risk("financial_transaction") == AgentRiskLevel.CRITICAL


def test_destructive_command_blocking():
    policy = PolicyEngine()
    risk = policy.evaluate_action_risk("execute_shell_command", parameters={"command": "rm -rf /"})
    assert risk == AgentRiskLevel.CRITICAL


def test_secret_sanitizer():
    raw_text = "Here is my token: gsk_123456789012345678901234567890123456789012345678"
    sanitized = Sanitizer.scrub_text(raw_text)
    assert "gsk_" not in sanitized
    assert "[REDACTED_SECRET]" in sanitized


@pytest.mark.asyncio
async def test_approval_engine_resolution():
    engine = ApprovalEngine()
    req = engine.create_request(
        task_id="task_test_01",
        action_type="delete_file",
        description="Delete file ./test.txt",
        risk_level=AgentRiskLevel.HIGH,
    )
    assert req.status == ApprovalStatus.PENDING

    # Resolve approval
    engine.resolve_decision(ApprovalDecision(request_id=req.id, decision=ApprovalStatus.APPROVED))
    status = await engine.wait_for_decision(req.id)
    assert status == ApprovalStatus.APPROVED
