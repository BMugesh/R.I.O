"""Unit tests for Verification Engine and Evidence collection."""
import pytest
pytestmark = pytest.mark.unit



import pytest
from packages.schemas.agents import Action, Evidence
from packages.schemas.tasks import TaskStep, VerificationStrategy
from services.verification.engine import VerificationEngine
from services.verification.evidence import EvidenceCollector


@pytest.mark.asyncio
async def test_file_verification_evidence(tmp_path):
    verifier = VerificationEngine()
    test_file = str(tmp_path / "verified_file.txt")

    step = TaskStep(
        name="Save Report",
        agent_id="filesystem_agent",
        action=Action(action_type="write_file", parameters={"path": test_file}),
        verification_strategy=VerificationStrategy(
            strategy_type="file_check",
            expected_state={"file_path": test_file},
        ),
    )

    # Before file creation: should fail verification
    is_verified_before = await verifier.verify_step(
        step,
        evidence_list=[EvidenceCollector.collect_file_evidence(test_file)],
    )
    assert is_verified_before is False

    # Create file
    with open(test_file, "w") as f:
        f.write("report content")

    # After file creation: must pass verification
    is_verified_after = await verifier.verify_step(
        step,
        evidence_list=[EvidenceCollector.collect_file_evidence(test_file)],
    )
    assert is_verified_after is True


@pytest.mark.asyncio
async def test_device_message_sent_verification():
    verifier = VerificationEngine()
    step = TaskStep(
        name="Send WhatsApp Message",
        agent_id="computer_agent",
        action=Action(action_type="send_message"),
        verification_strategy=VerificationStrategy(
            strategy_type="device_observation",
            expected_state={"verified": True},
        ),
    )

    ev = Evidence(
        type="device_observation",
        source="desktop_agent",
        data={"message_sent": True, "verified": True},
        confidence=0.95,
        verified=True,
    )
    is_verified = await verifier.verify_step(step, evidence_list=[ev])
    assert is_verified is True


@pytest.mark.asyncio
async def test_verification_result_schema():
    """Verify that VerificationResult contains all required Section 5 fields."""
    from services.verification.adaptive import AdaptiveVerifier, VerificationLevel

    step = TaskStep(
        name="Launch Chrome",
        agent_id="computer_agent",
        action=Action(action_type="open_application", parameters={"app_name": "chrome"}),
        verification_strategy=VerificationStrategy(
            strategy_type="device_observation",
            expected_state={"process_id": 18420},
        ),
    )

    ev = Evidence(
        type="device_observation",
        source="desktop_agent",
        data={"process_id": 18420, "window_title": "Google Chrome"},
        confidence=0.99,
        verified=True,
    )

    res = AdaptiveVerifier.evaluate(
        step=step,
        observation={"process_id": 18420, "window_title": "Google Chrome"},
        evidence_list=[ev],
        level=VerificationLevel.STANDARD,
    )

    assert hasattr(res, "verified")
    assert res.verified is True
    assert res.status == "verified"
    assert res.confidence >= 0.9
    assert len(res.evidence) == 1
    assert res.expected_state == {"process_id": 18420}
    assert res.observed_state["process_id"] == 18420
    assert res.reason is not None
    assert res.timestamp is not None


@pytest.mark.asyncio
async def test_verification_requires_evidence():
    """Verify that verification fails when evidence is absent or falsified."""
    from services.verification.adaptive import AdaptiveVerifier, VerificationLevel

    step = TaskStep(
        name="Check Nonexistent File",
        agent_id="filesystem_agent",
        action=Action(action_type="read_file", parameters={"path": "c:/nonexistent_file_xyz.txt"}),
        verification_strategy=VerificationStrategy(
            strategy_type="file_check",
            expected_state={"file_path": "c:/nonexistent_file_xyz.txt"},
        ),
    )

    # Empty evidence and false observation
    res = AdaptiveVerifier.evaluate(
        step=step,
        observation={"verified": True},  # Fake claim without backing
        evidence_list=[],
        level=VerificationLevel.STANDARD,
    )

    assert res.verified is False
    assert res.status == "failed"
    assert "File check failed" in res.reason


@pytest.mark.asyncio
async def test_no_fake_success():
    """Verify that raw observations claiming success without concrete attributes are rejected."""
    verifier = VerificationEngine()

    # Observation with just "success: True" and "verified: True" but no concrete observable state
    fake_obs = {"success": True, "verified": True}
    is_ok = await verifier.verify_observation(fake_obs, expected={"file_exists": True})
    assert is_ok is False

    # Failed observation must be rejected immediately
    failed_obs = {"status": "failed", "verified": False, "process_id": 1234}
    assert await verifier.verify_observation(failed_obs) is False


@pytest.mark.asyncio
async def test_verification_agent_real_audit(tmp_path):
    """Verify that VerificationAgent performs real physical disk check and reports truthfully."""
    from agents.verification.agent import VerificationAgent
    from packages.schemas.input import InputType, RIOInput
    from packages.schemas.agents import AgentStatus

    agent = VerificationAgent()
    real_file = tmp_path / "actual_evidence.txt"
    real_file.write_text("confirmed")

    # 1. Existing file -> SUCCESS
    in_real = RIOInput(type=InputType.TEXT, payload={"action_type": "verify_file", "file_path": str(real_file)})
    res_real = await agent.run(in_real, {})
    assert res_real.status == AgentStatus.SUCCESS
    assert res_real.data["verified"] is True
    assert res_real.evidence[0].verified is True

    # 2. Non-existent file -> FAILED
    fake_file = tmp_path / "ghost.txt"
    in_fake = RIOInput(type=InputType.TEXT, payload={"action_type": "verify_file", "file_path": str(fake_file)})
    res_fake = await agent.run(in_fake, {})
    assert res_fake.status == AgentStatus.FAILED
    assert res_fake.data["verified"] is False
    assert res_fake.evidence[0].verified is False

