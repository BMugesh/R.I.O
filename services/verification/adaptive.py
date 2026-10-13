"""Adaptive Verification Models & Evaluators for R.I.O. (Milestone 5).

Multi-level verification strategies, evidence-first evaluation, and confidence grading.
"""

from datetime import datetime, timezone
from enum import Enum
import os
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from packages.schemas.agents import Evidence
from packages.schemas.tasks import TaskStep, VerificationStrategy


class VerificationLevel(str, Enum):
    NONE = "none"          # Trivial actions without side-effects (read-only conversational)
    BASIC = "basic"        # Single check: process launched or confirmed positive evidence
    STANDARD = "standard"  # Single authoritative state check: file exists or DOM node matched
    STRICT = "strict"      # Multi-evidence check: file exists + non-empty, or element + text
    CRITICAL = "critical"  # Multi-source independent verification: process + window + handle


class VerificationResult(BaseModel):
    """Detailed verification outcome substantiated by concrete evidence."""

    verified: bool = False
    status: Literal["verified", "failed", "inconclusive"]
    confidence: float
    evidence: List[Evidence] = Field(default_factory=list)
    expected_state: Optional[Dict[str, Any]] = None
    observed_state: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    verification_level: VerificationLevel = VerificationLevel.STANDARD
    details: Dict[str, Any] = Field(default_factory=dict)


class AdaptiveVerifier:
    """Evaluates multi-source evidence against requested verification levels."""

    @classmethod
    def evaluate(
        cls,
        step: TaskStep,
        observation: Optional[Dict[str, Any]] = None,
        evidence_list: Optional[List[Evidence]] = None,
        level: Optional[VerificationLevel] = None,
    ) -> VerificationResult:
        """Perform evidence-first verification evaluation."""
        obs = observation or step.observation or {}
        evs = evidence_list or step.evidence or []
        req_level = level or (
            VerificationLevel(step.verification_level)
            if step.verification_level and step.verification_level in VerificationLevel._value2member_map_
            else VerificationLevel.STANDARD
        )

        expected_state = step.verification_strategy.expected_state if step.verification_strategy else None
        observed_state = dict(obs) if obs else None

        def make_result(
            status: Literal["verified", "failed", "inconclusive"],
            confidence: float,
            reason: str,
            details: Optional[Dict[str, Any]] = None,
        ) -> VerificationResult:
            return VerificationResult(
                verified=(status == "verified"),
                status=status,
                confidence=confidence,
                evidence=evs,
                expected_state=expected_state,
                observed_state=observed_state,
                reason=reason,
                timestamp=datetime.now(timezone.utc).isoformat(),
                verification_level=req_level,
                details=details or {},
            )

        # 1. Level: NONE
        if req_level == VerificationLevel.NONE:
            return make_result(
                status="verified",
                confidence=1.0,
                reason="Verification level is NONE; action has no external state requirements.",
            )

        # 2. Level: BASIC
        if req_level == VerificationLevel.BASIC:
            verified_evs = [e for e in evs if e.verified]
            if verified_evs:
                conf = max(e.confidence for e in verified_evs)
                return make_result(
                    status="verified",
                    confidence=conf,
                    reason=f"Basic check passed via {len(verified_evs)} verified evidence item(s).",
                )
            if obs.get("process_id") or obs.get("window_handle") or obs.get("file_exists") or obs.get("success") is True or obs.get("verified") is True:
                return make_result(
                    status="verified",
                    confidence=0.8,
                    reason="Basic check passed with concrete process or positive state observation.",
                )
            return make_result(
                status="failed",
                confidence=0.0,
                reason="Basic check failed: no verified evidence or observable system state.",
            )

        # 3. Level: STANDARD
        strategy = step.verification_strategy
        if req_level == VerificationLevel.STANDARD:
            if not strategy:
                high_conf = [e for e in evs if e.verified and e.confidence >= 0.8]
                if high_conf:
                    return make_result(
                        status="verified",
                        confidence=high_conf[0].confidence,
                        reason="Standard check verified via high-confidence evidence.",
                    )
                if not evs and not obs:
                    return make_result(
                        status="inconclusive",
                        confidence=0.3,
                        reason="No evidence or observations available to evaluate standard verification.",
                    )
                return make_result(
                    status="failed",
                    confidence=0.1,
                    reason="Standard verification failed: evidence does not substantiate completion.",
                )

            stype = strategy.strategy_type
            expected = strategy.expected_state or {}

            if stype == "file_check":
                target_path = expected.get("file_path") or expected.get("path") or obs.get("path") or obs.get("file_path") or obs.get("screenshot_path")
                file_evs = [e for e in evs if e.type == "file_check"]
                has_verified_ev = any(
                    e.verified and (
                        not target_path
                        or e.data.get("path") == target_path
                        or e.data.get("screenshot_path") == target_path
                        or e.data.get("file_exists") is True
                    ) for e in file_evs
                )
                real_exists = os.path.exists(target_path) if (target_path and isinstance(target_path, str)) else False
                if has_verified_ev or real_exists:
                    return make_result(
                        status="verified",
                        confidence=1.0,
                        reason=f"File existence verified at '{target_path or 'target'}'",
                    )
                return make_result(
                    status="failed",
                    confidence=0.0,
                    reason=f"File check failed: '{target_path}' does not exist.",
                )

            elif stype == "dom_query":
                selector = expected.get("selector") or expected.get("target")
                dom_evs = [e for e in evs if e.type in ("dom_element", "web_page")]
                has_verified_dom = any(
                    e.verified and (
                        not selector or selector == "body" or e.data.get("selector") == selector or e.data.get("target") == selector
                    ) for e in dom_evs
                )
                if has_verified_dom:
                    return make_result(
                        status="verified",
                        confidence=1.0,
                        reason=f"DOM element verified matching selector '{selector or 'target'}'",
                    )
                return make_result(
                    status="failed",
                    confidence=0.0,
                    reason=f"DOM element not found or not verified for selector '{selector}'",
                )

            elif stype in ("web_page", "browser_page"):
                web_evs = [e for e in evs if e.type in ("web_page", "browser")]
                has_verified_web = any(e.verified for e in web_evs)
                if has_verified_web or obs.get("verified"):
                    return make_result(
                        status="verified",
                        confidence=1.0,
                        reason=f"Web page loaded successfully: {obs.get('current_url') or 'url verified'}",
                    )
                return make_result(
                    status="failed",
                    confidence=0.0,
                    reason="Web page failed to load or verify.",
                )

            elif stype in ("device_observation", "system_telemetry"):
                dev_evs = [e for e in evs if e.type in ("device_observation", "system_telemetry")]
                has_verified_dev = any(e.verified for e in dev_evs)
                matches_expected = True
                if expected:
                    for k, v in expected.items():
                        if obs.get(k) != v:
                            ev_match = any(e.data.get(k) == v for e in dev_evs)
                            if not ev_match:
                                matches_expected = False
                                break
                if has_verified_dev and matches_expected:
                    return make_result(
                        status="verified",
                        confidence=0.95,
                        reason="Device observation matched expected state with verified evidence.",
                    )
                return make_result(
                    status="failed",
                    confidence=0.1,
                    reason="Device observation verification failed: expected state not matched.",
                )

            elif stype == "api_status":
                expected_code = expected.get("expected_status_code", 200)
                api_evs = [e for e in evs if e.type == "api_status" and e.data.get("status_code") == expected_code]
                if any(e.verified for e in api_evs) or obs.get("status_code") == expected_code:
                    return make_result(
                        status="verified",
                        confidence=1.0,
                        reason=f"API status code {expected_code} verified",
                    )
                return make_result(
                    status="failed",
                    confidence=0.0,
                    reason=f"API status check failed (expected {expected_code})",
                )

            # Default assertion check
            verified_evs = [e for e in evs if e.verified and e.confidence >= 0.8]
            matches_expected = True
            if expected:
                for k, v in expected.items():
                    if obs.get(k) != v and not any(e.data.get(k) == v for e in verified_evs):
                        matches_expected = False
                        break

            if verified_evs and matches_expected:
                return make_result(
                    status="verified",
                    confidence=0.9,
                    reason="State assertion matched verified observations.",
                )
            return make_result(
                status="failed",
                confidence=0.2,
                reason="Assertion verification failed: evidence or expected state mismatch.",
            )

        # 4. Level: STRICT
        if req_level == VerificationLevel.STRICT:
            verified_evs = [e for e in evs if e.verified and e.confidence >= 0.9]
            if not verified_evs:
                return make_result(
                    status="failed",
                    confidence=0.1,
                    reason="Strict check failed: no high-confidence verified evidence.",
                )

            for ev in verified_evs:
                if ev.type == "file_check":
                    fpath = ev.data.get("path")
                    real_size = os.path.getsize(fpath) if (fpath and os.path.exists(fpath)) else ev.data.get("size_bytes", 0)
                    if real_size > 0:
                        return make_result(
                            status="verified",
                            confidence=0.98,
                            reason=f"Strict check passed: file exists with non-zero size ({real_size} bytes).",
                        )
                elif ev.type == "dom_element":
                    if ev.data.get("matched_text") or ev.data.get("value") or ev.data.get("found"):
                        return make_result(
                            status="verified",
                            confidence=0.98,
                            reason="Strict check passed: DOM element found and attributes verified.",
                        )
                elif ev.type in ("api_status", "device_observation"):
                    return make_result(
                        status="verified",
                        confidence=0.95,
                        reason=f"Strict check passed for {ev.type}.",
                    )

            return make_result(
                status="inconclusive",
                confidence=0.5,
                reason="Strict verification inconclusive: primary check passed but secondary attributes missing.",
            )

        # 5. Level: CRITICAL
        if req_level == VerificationLevel.CRITICAL:
            verified_evs = [e for e in evs if e.verified and e.confidence >= 0.85]
            if len(verified_evs) >= 2:
                return make_result(
                    status="verified",
                    confidence=0.99,
                    reason=f"Critical verification passed with {len(verified_evs)} independent evidence proofs.",
                )
            elif len(verified_evs) == 1:
                return make_result(
                    status="inconclusive",
                    confidence=0.6,
                    reason="Critical verification requires at least 2 independent evidence proofs (found 1).",
                )
            else:
                return make_result(
                    status="failed",
                    confidence=0.0,
                    reason="Critical verification failed: zero verified evidence proofs.",
                )
