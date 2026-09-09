"""Unit tests for Verification Engine and Evidence collection."""

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
        data={"message_sent": True},
        confidence=0.95,
        verified=True,
    )
    is_verified = await verifier.verify_step(step, evidence_list=[ev])
    assert is_verified is True
