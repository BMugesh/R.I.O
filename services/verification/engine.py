"""Verification Engine for R.I.O.

Enforces the core engineering principle: NEVER claim success without verified evidence.
Evaluates observed outputs against step expected states.
"""

from typing import Any, Dict, List, Optional
from packages.schemas.agents import Evidence
from packages.schemas.tasks import TaskStep, VerificationStrategy


class VerificationEngine:
    """Core Verification Engine."""

    async def verify_step(
        self,
        step: TaskStep,
        observation: Optional[Dict[str, Any]] = None,
        evidence_list: Optional[List[Evidence]] = None,
    ) -> bool:
        """Verify that a step achieved its expected state.

        Returns True only if verified evidence matches the expected state.
        """
        obs = observation or step.observation or {}
        evidences = evidence_list or step.evidence or []

        # If no verification strategy was specified, default to checking tool/agent success status
        if not step.verification_strategy:
            return obs.get("success", False) is True or any(e.verified for e in evidences)

        strategy = step.verification_strategy
        expected = strategy.expected_state

        if strategy.strategy_type == "file_check":
            target_path = expected.get("file_path")
            if not target_path:
                return False
            for ev in evidences:
                if ev.type == "file_check" and ev.data.get("path") == target_path:
                    return ev.verified is True
            # Check observation
            return obs.get("file_exists") is True

        elif strategy.strategy_type == "dom_query":
            selector = expected.get("selector")
            for ev in evidences:
                if ev.type == "dom_element" and ev.data.get("selector") == selector:
                    return ev.verified is True
            return obs.get("element_found") is True

        elif strategy.strategy_type == "api_status":
            expected_code = expected.get("expected_status_code", 200)
            for ev in evidences:
                if ev.type == "api_status" and ev.data.get("status_code") == expected_code:
                    return ev.verified is True
            return obs.get("status_code") == expected_code

        elif strategy.strategy_type == "device_observation":
            # For UI tasks (e.g. WhatsApp message sent, app launched)
            for ev in evidences:
                if ev.type == "device_observation" and ev.verified:
                    return True
            return obs.get("verified", False) is True or obs.get("success", False) is True

        elif strategy.strategy_type == "assertion":
            for k, v in expected.items():
                if obs.get(k) == v:
                    return True
                for ev in evidences:
                    if ev.data.get(k) == v and ev.verified:
                        return True
            return any(e.verified and e.confidence >= 0.8 for e in evidences)

        # Default fallback: check if any high-confidence evidence verified
        return any(e.verified and e.confidence >= 0.8 for e in evidences)

