"""Verification Engine for R.I.O.

Enforces the core engineering principle: NEVER claim success without verified evidence.
Evaluates observed outputs against step expected states.
"""

from typing import Any, Dict, List, Optional
from packages.schemas.agents import Evidence
from packages.schemas.tasks import TaskStep, VerificationStrategy
from services.verification.adaptive import AdaptiveVerifier, VerificationLevel, VerificationResult


class VerificationEngine:
    """Core Verification Engine with Adaptive Multi-Level Evidence Evaluation."""

    async def verify_step_adaptive(
        self,
        step: TaskStep,
        observation: Optional[Dict[str, Any]] = None,
        evidence_list: Optional[List[Evidence]] = None,
        level: Optional[VerificationLevel] = None,
    ) -> VerificationResult:
        """Evaluate evidence against verification requirements and return detailed result."""
        return AdaptiveVerifier.evaluate(
            step=step,
            observation=observation,
            evidence_list=evidence_list,
            level=level,
        )

    async def verify_step(
        self,
        step: TaskStep,
        observation: Optional[Dict[str, Any]] = None,
        evidence_list: Optional[List[Evidence]] = None,
    ) -> bool:
        """Verify that a step achieved its expected state.

        Returns True only if verified evidence matches the expected state.
        """
        res = await self.verify_step_adaptive(step=step, observation=observation, evidence_list=evidence_list)
        return res.verified and res.status == "verified"

    async def verify_observation(self, observation: Dict[str, Any], expected: Optional[Dict[str, Any]] = None) -> bool:
        """Helper to evaluate raw observation dict against expected state."""
        if not observation:
            return False
        if observation.get("status") == "failed" or observation.get("verified") is False or observation.get("error"):
            return False
        if expected:
            for k, v in expected.items():
                if observation.get(k) != v:
                    return False
            return True
        # Without explicit expected state, must possess concrete observable attributes
        has_concrete_state = any(
            k in observation for k in (
                "file_exists", "process_id", "window_handle", "window_title",
                "current_url", "element_found", "message_sent", "output", "data"
            )
        )
        return has_concrete_state and observation.get("verified", False) is True

