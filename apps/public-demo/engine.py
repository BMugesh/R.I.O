"""Deterministic Policy Engine and Isolated Sandbox Execution Engine for R.I.O. public demo."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional
from fastapi import HTTPException, status

from planner import (
    PlanDraft,
    SANDBOX_DOCUMENTS,
    generate_candidate_plan,
    get_scenario_by_id,
)
from schemas import (
    AllowedActionInfo,
    CalibrationDimensions,
    DecisionChoice,
    DecisionRequest,
    DemoSessionResponse,
    EvidenceRecord,
    ExecutionEvent,
    ExecutionPlan,
    InterruptCommand,
    InterruptRequest,
    PendingApproval,
    PlanStep,
    RiskLevel,
    SandboxActionId,
    SessionControls,
    SessionStatus,
    SimulatedArtifact,
    StepStatus,
    TrustSummary,
)
from security import (
    generate_session_id,
    generate_short_id,
    get_max_interactions_per_session,
    get_max_steps_per_session,
    get_step_delay_seconds,
    sanitize_text,
)
from session_store import SessionRecord, session_store


SIMULATION_NOTICE = (
    "ISOLATED RESEARCH SANDBOX: All actions are simulated against 3 synthetic documents. "
    "No local files, shell commands, desktop controls, personal devices, or external APIs are accessed."
)


@dataclass(frozen=True)
class PolicySpec:
    action_id: SandboxActionId
    label: str
    risk: RiskLevel
    requires_approval: bool
    policy_rule_id: str
    sandbox_target: str
    if_approved: str = "Proceeds with the simulated sandbox operation."
    if_rejected: str = "Halts execution safely and skips dependent downstream actions."


POLICY_CATALOG: Dict[SandboxActionId, PolicySpec] = {
    SandboxActionId.ANALYSE_TASK: PolicySpec(
        action_id=SandboxActionId.ANALYSE_TASK,
        label="Analyse task",
        risk=RiskLevel.LOW,
        requires_approval=False,
        policy_rule_id="SANDBOX_INTENT_PARSE",
        sandbox_target="sandbox://task-parser",
    ),
    SandboxActionId.READ_SAMPLE_DOCUMENTS: PolicySpec(
        action_id=SandboxActionId.READ_SAMPLE_DOCUMENTS,
        label="Read sample documents",
        risk=RiskLevel.LOW,
        requires_approval=False,
        policy_rule_id="SANDBOX_READ_ONLY",
        sandbox_target="sandbox://docs/synthetic-corpus-3",
    ),
    SandboxActionId.INSPECT_SANDBOX_DATASET: PolicySpec(
        action_id=SandboxActionId.INSPECT_SANDBOX_DATASET,
        label="Inspect sandbox dataset",
        risk=RiskLevel.LOW,
        requires_approval=False,
        policy_rule_id="SANDBOX_READ_ONLY",
        sandbox_target="sandbox://telemetry/synthetic-metrics",
    ),
    SandboxActionId.EXTRACT_KEY_CLAIMS: PolicySpec(
        action_id=SandboxActionId.EXTRACT_KEY_CLAIMS,
        label="Extract key claims",
        risk=RiskLevel.MEDIUM,
        requires_approval=False,
        policy_rule_id="SYNTHETIC_EXTRACTION",
        sandbox_target="sandbox://workspace/claims-buffer",
    ),
    SandboxActionId.VERIFY_CITATIONS: PolicySpec(
        action_id=SandboxActionId.VERIFY_CITATIONS,
        label="Verify citations",
        risk=RiskLevel.LOW,
        requires_approval=False,
        policy_rule_id="CITATION_CROSS_CHECK",
        sandbox_target="sandbox://docs/citation-index",
    ),
    SandboxActionId.GENERATE_COMPARISON: PolicySpec(
        action_id=SandboxActionId.GENERATE_COMPARISON,
        label="Generate comparison",
        risk=RiskLevel.MEDIUM,
        requires_approval=False,
        policy_rule_id="SYNTHETIC_SYNTHESIS",
        sandbox_target="sandbox://workspace/comparison-draft",
    ),
    SandboxActionId.DRAFT_BRIEFING: PolicySpec(
        action_id=SandboxActionId.DRAFT_BRIEFING,
        label="Draft trust briefing",
        risk=RiskLevel.MEDIUM,
        requires_approval=False,
        policy_rule_id="SYNTHETIC_SYNTHESIS",
        sandbox_target="sandbox://workspace/briefing-draft",
    ),
    SandboxActionId.RUN_POLICY_AUDIT: PolicySpec(
        action_id=SandboxActionId.RUN_POLICY_AUDIT,
        label="Run policy audit",
        risk=RiskLevel.LOW,
        requires_approval=False,
        policy_rule_id="SANDBOX_BOUNDARY_AUDIT",
        sandbox_target="sandbox://policy/allowlist-evaluator",
    ),
    SandboxActionId.EXPORT_REPORT: PolicySpec(
        action_id=SandboxActionId.EXPORT_REPORT,
        label="Approve report export",
        risk=RiskLevel.HIGH,
        requires_approval=True,
        policy_rule_id="HUMAN_APPROVAL_REQUIRED",
        sandbox_target="sandbox://export-gate/simulated-report",
        if_approved="Authorizes recording the simulated report artifact inside ephemeral demo memory.",
        if_rejected="Rejects export, leaves draft unpublished in memory only, and skips finalization.",
    ),
    SandboxActionId.PUBLISH_SUMMARY: PolicySpec(
        action_id=SandboxActionId.PUBLISH_SUMMARY,
        label="Approve briefing publish",
        risk=RiskLevel.HIGH,
        requires_approval=True,
        policy_rule_id="HUMAN_APPROVAL_REQUIRED",
        sandbox_target="sandbox://publish-gate/simulated-briefing",
        if_approved="Authorizes simulated publication inside this isolated demo session.",
        if_rejected="Rejects simulated publication and prevents downstream recording.",
    ),
    SandboxActionId.APPLY_MITIGATION_PLAN: PolicySpec(
        action_id=SandboxActionId.APPLY_MITIGATION_PLAN,
        label="Approve mitigation plan",
        risk=RiskLevel.HIGH,
        requires_approval=True,
        policy_rule_id="HUMAN_APPROVAL_REQUIRED",
        sandbox_target="sandbox://policy-gate/simulated-mitigation",
        if_approved="Applies simulated policy hardening rules inside the sandbox audit log.",
        if_rejected="Declines policy mutation and leaves sandbox baseline unchanged.",
    ),
    SandboxActionId.COMPLETE_SIMULATED_EXPORT: PolicySpec(
        action_id=SandboxActionId.COMPLETE_SIMULATED_EXPORT,
        label="Complete simulated export",
        risk=RiskLevel.LOW,
        requires_approval=False,
        policy_rule_id="SIMULATED_LOCAL_RECORD",
        sandbox_target="sandbox://session-memory/artifact",
    ),
}


def get_allowed_actions_info() -> List[AllowedActionInfo]:
    return [
        AllowedActionInfo(
            action_id=spec.action_id,
            label=spec.label,
            risk=spec.risk,
            requires_approval=spec.requires_approval,
            policy_rule_id=spec.policy_rule_id,
            sandbox_target=spec.sandbox_target,
        )
        for spec in POLICY_CATALOG.values()
    ]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _append_event(
    rec: SessionRecord,
    event_type: str,
    status_str: str,
    summary: str,
    step_id: Optional[str] = None,
    action_id: Optional[str] = None,
    risk: Optional[RiskLevel] = None,
    policy_rule_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> ExecutionEvent:
    rec.event_seq_counter += 1
    evt = ExecutionEvent(
        seq=rec.event_seq_counter,
        event_id=generate_short_id("evt"),
        timestamp=_iso_now(),
        event_type=event_type,
        step_id=step_id,
        action_id=action_id,
        risk=risk,
        policy_rule_id=policy_rule_id,
        status=status_str,
        summary=summary,
        metadata=metadata or {},
    )
    rec.events.append(evt)
    return evt


def apply_deterministic_policy(draft: PlanDraft) -> ExecutionPlan:
    """Enforce deterministic risk tiers, approval gates, and valid forward DAG dependencies."""
    max_steps = get_max_steps_per_session()
    draft_steps = list(draft.steps[:max_steps])

    has_gate = any(POLICY_CATALOG[s.action_id].requires_approval for s in draft_steps)
    if not has_gate:
        if len(draft_steps) >= max_steps:
            draft_steps = draft_steps[: max_steps - 1]
        insert_idx = max(0, len(draft_steps) - 1)
        gate_step = type(draft_steps[0])(
            action_id=SandboxActionId.EXPORT_REPORT,
            title="Approve report export",
            description="Pause execution and wait for visitor approval before simulated export.",
            reasoning_summary="Policy enforces an explicit human approval gate before recording final artifacts.",
            depends_on_indices=[insert_idx - 1] if insert_idx > 0 else [],
        )
        draft_steps.insert(insert_idx, gate_step)
        if len(draft_steps) > insert_idx + 1:
            draft_steps[insert_idx + 1].depends_on_indices = [insert_idx]

    # Ensure at least one post-gate completion step exists after the final gated step
    # so human approval/rejection always governs downstream finalization.
    if draft_steps and POLICY_CATALOG[draft_steps[-1].action_id].requires_approval:
        if len(draft_steps) >= max_steps:
            gate_step = draft_steps[-1]
            draft_steps = draft_steps[: max_steps - 2] + [gate_step]
        gate_idx = len(draft_steps) - 1
        draft_steps.append(
            type(draft_steps[0])(
                action_id=SandboxActionId.COMPLETE_SIMULATED_EXPORT,
                title="Complete simulated export",
                description="Record the final simulated artifact inside ephemeral session memory.",
                reasoning_summary="Completes the simulated workflow only after explicit human approval.",
                depends_on_indices=[gate_idx],
            )
        )

    plan_steps: List[PlanStep] = []
    gated_step_id: Optional[str] = None

    for idx, step_draft in enumerate(draft_steps):
        spec = POLICY_CATALOG[step_draft.action_id]
        step_id = f"step_{idx + 1}"
        depends_on = [
            f"step_{dep_idx + 1}"
            for dep_idx in step_draft.depends_on_indices
            if 0 <= dep_idx < idx
        ]
        if idx > 0 and not depends_on:
            depends_on = [f"step_{idx}"]

        if spec.requires_approval:
            gated_step_id = step_id
        elif gated_step_id and gated_step_id not in depends_on:
            depends_on.append(gated_step_id)

        plan_steps.append(
            PlanStep(
                step_id=step_id,
                order=idx + 1,
                action_id=step_draft.action_id,
                title=step_draft.title,
                description=step_draft.description,
                reasoning_summary=step_draft.reasoning_summary,
                depends_on=depends_on,
                risk=spec.risk,
                requires_approval=spec.requires_approval,
                policy_rule_id=spec.policy_rule_id,
                sandbox_target=spec.sandbox_target,
                status=StepStatus.PENDING,
            )
        )

    return ExecutionPlan(
        plan_id=generate_short_id("plan"),
        goal_summary=draft.goal_summary,
        planner_source=draft.planner_source,  # type: ignore[arg-type]
        planner_model=draft.planner_model,
        fallback_reason=draft.fallback_reason,
        boundary_triggered=draft.boundary_triggered,
        boundary_note=draft.boundary_note,
        steps=plan_steps,
    )


def _build_comparison_markdown(
    task: str,
    artifact_state: Literal[
        "draft_pending_approval",
        "export_approved_simulated",
        "export_rejected_draft_only",
        "cancelled_draft_only",
    ],
    boundary_triggered: bool,
) -> str:
    state_line = {
        "draft_pending_approval": "Draft generated in session memory (awaiting human export approval; external publication not performed).",
        "export_approved_simulated": "Export approved by visitor and recorded inside ephemeral demo session memory (external publication not performed).",
        "export_rejected_draft_only": "Export action REJECTED by human visitor. Draft held in session memory only; external publication NOT performed.",
        "cancelled_draft_only": "Session CANCELLED before export approval. Draft held in session memory only; external publication NOT performed.",
    }[artifact_state]

    if boundary_triggered:
        return (
            "### Sandbox Policy Boundary Audit Draft\n\n"
            f"**Visitor Request:** `{task}`\n\n"
            "**Policy Decision:** Blocked privileged host/network intents under `SANDBOX_BOUNDARY_ENFORCED`.\n\n"
            "| Capability Requested | Public Sandbox Status | Reason |\n"
            "|---|---|---|\n"
            "| Host Filesystem / OS Shell | Blocked | Isolated container has no access to personal laptop files |\n"
            "| Credentials / Secrets | Blocked | Secret access prohibited in anonymous demo |\n"
            "| External Messaging / Email | Blocked | Outbound network mutations disabled |\n"
            "| Synthetic Policy Audit | Allowed (Simulated) | Read-only diagnostic generated in session memory |\n\n"
            f"**Export Status:** {state_line}"
        )

    return (
        "### Synthesized Sandbox Comparison Draft\n\n"
        f"**Task:** {task}\n\n"
        "| Study | Primary Metric | Safety / Oversight Finding | Caveat |\n"
        "|---|---|---|---|\n"
        "| `[DOC-01]` Guarded Autonomy (2025-11) | Task Success: **84.2%** | Unsafe leakage **1.4%**; indiscriminate gating caused **22.0%** fatigue | 120 synthetic desktop workflows only |\n"
        "| `[DOC-02]` Calibrated Displays (2026-02) | Over-Reliance: **-31.5%** | Appropriate intervention **79.6%** (+6.4s review overhead) | 48-person lab study; short horizon |\n"
        "| `[DOC-03]` Policy Sandboxes (2026-06) | Policy Violations: **0.0%** | Decoupling LLM planner from allowlist kept violations at 0% (42 ms eval) | Bounded to 12-18 allowlisted actions |\n\n"
        "**Cross-Document Takeaway:** Combining risk-tiered approval gates (`DOC-01`), uncertainty displays (`DOC-02`), "
        "and allowlisted deterministic policy enforcement (`DOC-03`) balances safety and human oversight overhead.\n\n"
        f"**Export Status:** {state_line}"
    )


def _apply_step_outputs_and_record_event(rec: SessionRecord, step: PlanStep) -> ExecutionEvent:
    """Execute simulated step side-effects, emit step_completed event, and attach traceable evidence."""
    action = step.action_id
    step.completed_at = _iso_now()
    step.status = StepStatus.COMPLETED
    all_doc_ids = [d.doc_id for d in SANDBOX_DOCUMENTS]

    if action == SandboxActionId.ANALYSE_TASK:
        step.output_summary = (
            "Task decomposed into bounded sandbox workflow; all non-sandbox capabilities excluded."
        )
        rec.what_rio_did.append(
            f"Parsed task constraints and mapped plan to {len(rec.plan.steps)} allowlisted sandbox steps."
        )
        evt = _append_event(
            rec,
            event_type="step_completed",
            status_str="completed",
            summary=step.output_summary,
            step_id=step.step_id,
            action_id=action.value,
            risk=step.risk,
            policy_rule_id=step.policy_rule_id,
        )
        rec.evidence.append(
            EvidenceRecord(
                evidence_id=generate_short_id("ev"),
                step_id=step.step_id,
                action_id=action.value,
                event_id=evt.event_id,
                event_seq=evt.seq,
                policy_rule_id=step.policy_rule_id,
                document_ids=[],
                source="sandbox://task-parser",
                verification_status="verified_rule",
                certainty_kind="deterministic_policy_check",
                certainty_label="Deterministic Check (Rule Verified)",
                excerpt=f"Validated task length ({len(rec.task)} chars <= 300) and allowlist constraint compliance.",
            )
        )
        return evt

    if action in (SandboxActionId.READ_SAMPLE_DOCUMENTS, SandboxActionId.INSPECT_SANDBOX_DATASET):
        doc_ids_str = ", ".join(all_doc_ids)
        step.output_summary = f"Loaded 3 synthetic sandbox documents ({doc_ids_str}) in read-only mode."
        rec.what_rio_did.append(
            f"Read 3 synthetic sandbox sources ({doc_ids_str}) with zero host filesystem access."
        )
        rec.calibration_dimensions.cited_document_ids = list(all_doc_ids)
        rec.calibration_dimensions.evidence_completeness_label = (
            "3 / 3 synthetic sandbox documents read (0 external sources)"
        )
        evt = _append_event(
            rec,
            event_type="step_completed",
            status_str="completed",
            summary=step.output_summary,
            step_id=step.step_id,
            action_id=action.value,
            risk=step.risk,
            policy_rule_id=step.policy_rule_id,
            metadata={"document_ids": all_doc_ids},
        )
        rec.evidence.append(
            EvidenceRecord(
                evidence_id=generate_short_id("ev"),
                step_id=step.step_id,
                action_id=action.value,
                event_id=evt.event_id,
                event_seq=evt.seq,
                policy_rule_id=step.policy_rule_id,
                document_ids=list(all_doc_ids),
                source="sandbox://docs/synthetic-corpus-3",
                verification_status="synthetic_source",
                certainty_kind="synthetic_corpus_read",
                certainty_label="Synthetic Corpus Read (3/3 Docs)",
                excerpt="DOC-01 (n=120 workflows, 1.4% leakage), DOC-02 (-31.5% over-reliance), DOC-03 (0.0% policy violations).",
            )
        )
        return evt

    if action in (SandboxActionId.VERIFY_CITATIONS, SandboxActionId.EXTRACT_KEY_CLAIMS):
        step.output_summary = "Cross-checked quantitative metrics and extracted explicit study caveats."
        rec.what_rio_did.append(
            "Verified claims against DOC-01, DOC-02, and DOC-03 and extracted sample-size caveats."
        )
        rec.calibration_dimensions.cited_document_ids = list(all_doc_ids)
        rec.calibration_dimensions.evidence_completeness_label = (
            "3 / 3 synthetic sandbox documents cross-checked (0 external sources)"
        )
        evt = _append_event(
            rec,
            event_type="step_completed",
            status_str="completed",
            summary=step.output_summary,
            step_id=step.step_id,
            action_id=action.value,
            risk=step.risk,
            policy_rule_id=step.policy_rule_id,
            metadata={"document_ids": all_doc_ids},
        )
        rec.evidence.append(
            EvidenceRecord(
                evidence_id=generate_short_id("ev"),
                step_id=step.step_id,
                action_id=action.value,
                event_id=evt.event_id,
                event_seq=evt.seq,
                policy_rule_id=step.policy_rule_id,
                document_ids=list(all_doc_ids),
                source="sandbox://docs/citation-index",
                verification_status="synthetic_source",
                certainty_kind="synthetic_corpus_read",
                certainty_label="Citation Check (3/3 Synthetic Docs)",
                excerpt="All 3 citations matched synthetic corpus metadata; caveats preserved without external fact-checking.",
            )
        )
        return evt

    if action in (SandboxActionId.GENERATE_COMPARISON, SandboxActionId.DRAFT_BRIEFING):
        step.output_summary = (
            "Generated unexported synthesis draft in session memory citing DOC-01, DOC-02, and DOC-03."
        )
        rec.what_rio_did.append(
            "Generated draft synthesis in ephemeral session memory (not yet approved for export)."
        )
        rec.calibration_dimensions.cited_document_ids = list(all_doc_ids)
        rec.calibration_dimensions.evidence_completeness_label = (
            "3 / 3 synthetic sandbox documents cited in draft (0 external sources)"
        )
        rec.calibration_dimensions.model_certainty_label = "unvalidated_synthetic_synthesis"
        rec.calibration_dimensions.model_certainty_note = (
            "Synthesis draft is generated within the 3-document synthetic sandbox and has NOT been externally fact-checked."
        )
        rec.calibration_label = "policy_and_corpus_grounded"
        rec.simulated_artifact = SimulatedArtifact(
            artifact_id=generate_short_id("art"),
            title="In-Memory Synthesis Draft (Pending Export Approval)",
            artifact_state="draft_pending_approval",
            draft_created_in_memory=True,
            export_approved=False,
            external_publication_performed=False,
            simulated_only=True,
            notice=(
                "DRAFT IN SESSION MEMORY ONLY — Export approval pending; external publication not performed."
            ),
            content=_build_comparison_markdown(
                rec.task,
                artifact_state="draft_pending_approval",
                boundary_triggered=rec.plan.boundary_triggered,
            ),
            citations=list(all_doc_ids),
        )
        evt = _append_event(
            rec,
            event_type="step_completed",
            status_str="completed",
            summary=step.output_summary,
            step_id=step.step_id,
            action_id=action.value,
            risk=step.risk,
            policy_rule_id=step.policy_rule_id,
            metadata={"document_ids": all_doc_ids, "artifact_state": "draft_pending_approval"},
        )
        rec.evidence.append(
            EvidenceRecord(
                evidence_id=generate_short_id("ev"),
                step_id=step.step_id,
                action_id=action.value,
                event_id=evt.event_id,
                event_seq=evt.seq,
                policy_rule_id=step.policy_rule_id,
                document_ids=list(all_doc_ids),
                source=step.sandbox_target,
                verification_status="unvalidated_draft",
                certainty_kind="heuristic_synthesis",
                certainty_label="Unvalidated Draft (Synthetic Corpus Only)",
                excerpt="Draft generated in session memory from DOC-01..DOC-03; factual generalizability unverified.",
            )
        )
        return evt

    if action == SandboxActionId.RUN_POLICY_AUDIT:
        step.output_summary = (
            "Evaluated request against deterministic allowlist; confirmed privileged capabilities remain isolated."
        )
        rec.what_rio_did.append(
            "Ran deterministic policy audit verifying zero host, shell, secret, or external network permissions."
        )
        rec.simulated_artifact = SimulatedArtifact(
            artifact_id=generate_short_id("art"),
            title="In-Memory Policy Boundary Audit Draft (Pending Export Approval)",
            artifact_state="draft_pending_approval",
            draft_created_in_memory=True,
            export_approved=False,
            external_publication_performed=False,
            simulated_only=True,
            notice=(
                "AUDIT DRAFT IN SESSION MEMORY ONLY — Export approval pending; external publication not performed."
            ),
            content=_build_comparison_markdown(
                rec.task,
                artifact_state="draft_pending_approval",
                boundary_triggered=True,
            ),
            citations=[],
        )
        evt = _append_event(
            rec,
            event_type="step_completed",
            status_str="completed",
            summary=step.output_summary,
            step_id=step.step_id,
            action_id=action.value,
            risk=step.risk,
            policy_rule_id=step.policy_rule_id,
        )
        rec.evidence.append(
            EvidenceRecord(
                evidence_id=generate_short_id("ev"),
                step_id=step.step_id,
                action_id=action.value,
                event_id=evt.event_id,
                event_seq=evt.seq,
                policy_rule_id=step.policy_rule_id,
                document_ids=[],
                source="sandbox://policy/allowlist-evaluator",
                verification_status="blocked_by_policy" if rec.plan.boundary_triggered else "verified_rule",
                certainty_kind="deterministic_policy_check",
                certainty_label="Deterministic Policy Check (Boolean)",
                excerpt=rec.plan.boundary_note or "All steps conform to the 12-action deterministic sandbox allowlist.",
            )
        )
        return evt

    if action in (
        SandboxActionId.EXPORT_REPORT,
        SandboxActionId.PUBLISH_SUMMARY,
        SandboxActionId.APPLY_MITIGATION_PLAN,
    ):
        step.output_summary = (
            f"Human approval granted for '{action.value}'; simulated export step unlocked."
        )
        rec.what_rio_did.append(
            f"Obtained explicit visitor approval for high-risk gated action '{action.value}'."
        )
        rec.why_decisions_made.append(
            f"Human approval satisfied {step.policy_rule_id} for '{action.value}', permitting simulated completion."
        )
        evt = _append_event(
            rec,
            event_type="step_completed",
            status_str="completed",
            summary=step.output_summary,
            step_id=step.step_id,
            action_id=action.value,
            risk=step.risk,
            policy_rule_id=step.policy_rule_id,
        )
        rec.evidence.append(
            EvidenceRecord(
                evidence_id=generate_short_id("ev"),
                step_id=step.step_id,
                action_id=action.value,
                event_id=evt.event_id,
                event_seq=evt.seq,
                policy_rule_id=step.policy_rule_id,
                document_ids=list(rec.calibration_dimensions.cited_document_ids),
                source="human://visitor-approval-gate",
                verification_status="verified_rule",
                certainty_kind="human_decision_record",
                certainty_label="Human Gate Approved (Audit Record)",
                excerpt=f"Visitor explicitly authorized '{action.value}' at {step.completed_at}; authorization does not assert external accuracy.",
            )
        )
        return evt

    # COMPLETE_SIMULATED_EXPORT
    step.output_summary = (
        "Simulated export approved and recorded inside ephemeral session memory. External publication not performed."
    )
    rec.what_rio_did.append(
        "Recorded simulated export inside ephemeral session memory after approval; zero external transmission."
    )
    cited = [] if rec.plan.boundary_triggered else list(all_doc_ids)
    rec.simulated_artifact = SimulatedArtifact(
        artifact_id=generate_short_id("art"),
        title=(
            "Simulated Policy Boundary Audit (Export Approved — In-Memory)"
            if rec.plan.boundary_triggered
            else "Simulated Research Comparison Report (Export Approved — In-Memory)"
        ),
        artifact_state="export_approved_simulated",
        draft_created_in_memory=True,
        export_approved=True,
        external_publication_performed=False,
        simulated_only=True,
        notice=(
            "SIMULATED EXPORT APPROVED — Recorded in ephemeral 30-minute session memory only. External publication NOT performed."
        ),
        content=_build_comparison_markdown(
            rec.task,
            artifact_state="export_approved_simulated",
            boundary_triggered=rec.plan.boundary_triggered,
        ),
        citations=cited,
    )
    rec.calibration_dimensions.execution_certainty_label = "simulated_in_memory_only"
    rec.calibration_dimensions.execution_certainty_note = (
        "Simulated export completed in ephemeral session memory after human approval; external publication not performed."
    )
    evt = _append_event(
        rec,
        event_type="step_completed",
        status_str="completed",
        summary=step.output_summary,
        step_id=step.step_id,
        action_id=action.value,
        risk=step.risk,
        policy_rule_id=step.policy_rule_id,
        metadata={"document_ids": cited, "artifact_state": "export_approved_simulated"},
    )
    rec.evidence.append(
        EvidenceRecord(
            evidence_id=generate_short_id("ev"),
            step_id=step.step_id,
            action_id=action.value,
            event_id=evt.event_id,
            event_seq=evt.seq,
            policy_rule_id=step.policy_rule_id,
            document_ids=cited,
            source="sandbox://session-memory/artifact",
            verification_status="verified_rule",
            certainty_kind="deterministic_policy_check",
            certainty_label="Simulated Export Recorded (In-Memory Only)",
            excerpt="Export recorded in ephemeral session memory following gate approval; external I/O remained disabled.",
        )
    )
    return evt


def _find_next_ready_step(rec: SessionRecord) -> Optional[PlanStep]:
    completed_ids = {s.step_id for s in rec.plan.steps if s.status == StepStatus.COMPLETED}
    for step in rec.plan.steps:
        if step.status == StepStatus.PENDING and all(dep in completed_ids for dep in step.depends_on):
            return step
    return None


def _enter_waiting_for_approval(rec: SessionRecord, step: PlanStep) -> None:
    spec = POLICY_CATALOG[step.action_id]
    now = _iso_now()
    step.status = StepStatus.WAITING_FOR_HUMAN
    step.started_at = step.started_at or now
    rec.status = SessionStatus.WAITING_FOR_HUMAN
    rec.pending_approval = PendingApproval(
        approval_id=generate_short_id("apr"),
        step_id=step.step_id,
        action_id=step.action_id,
        title=step.title,
        description=step.description,
        risk=step.risk,
        policy_rule_id=step.policy_rule_id,
        sandbox_target=step.sandbox_target,
        if_approved=spec.if_approved,
        if_rejected=spec.if_rejected,
        requested_at=now,
    )
    rec.why_decisions_made.append(
        f"Paused before '{step.action_id.value}' because policy rule {step.policy_rule_id} classifies it as {step.risk.value.upper()} risk."
    )
    _append_event(
        rec,
        event_type="approval_requested",
        status_str="waiting_for_human",
        summary=f"Execution paused at '{step.title}' awaiting human decision on '{step.action_id.value}'.",
        step_id=step.step_id,
        action_id=step.action_id.value,
        risk=step.risk,
        policy_rule_id=step.policy_rule_id,
        metadata={"approval_id": rec.pending_approval.approval_id},
    )


def _advance_step_locked(rec: SessionRecord) -> bool:
    """Complete currently running step and start next ready step or pause at approval gate."""
    running_step = next((s for s in rec.plan.steps if s.status == StepStatus.RUNNING), None)
    if running_step is not None:
        _apply_step_outputs_and_record_event(rec, running_step)

    next_step = _find_next_ready_step(rec)
    if next_step is None:
        rec.status = SessionStatus.COMPLETED
        rec.updated_at = datetime.now(timezone.utc)
        _append_event(
            rec,
            event_type="session_completed",
            status_str="completed",
            summary="All allowed sandbox workflow steps completed.",
        )
        return False

    if next_step.requires_approval:
        _enter_waiting_for_approval(rec, next_step)
        rec.updated_at = datetime.now(timezone.utc)
        return False

    next_step.status = StepStatus.RUNNING
    next_step.started_at = _iso_now()
    rec.status = SessionStatus.RUNNING
    rec.updated_at = datetime.now(timezone.utc)
    _append_event(
        rec,
        event_type="step_started",
        status_str="running",
        summary=f"Executing '{next_step.title}': {next_step.description}",
        step_id=next_step.step_id,
        action_id=next_step.action_id.value,
        risk=next_step.risk,
        policy_rule_id=next_step.policy_rule_id,
    )
    return True


def _advance_until_gate_or_done_locked(rec: SessionRecord) -> None:
    while rec.status == SessionStatus.RUNNING:
        if not _advance_step_locked(rec):
            break


async def _run_session_loop(session_id: str, delay_seconds: float) -> None:
    my_task = asyncio.current_task()
    try:
        while True:
            await asyncio.sleep(delay_seconds)
            try:
                rec = session_store.get(session_id)
            except HTTPException:
                return

            async with rec.lock:
                if rec.runner_task is not my_task or rec.status != SessionStatus.RUNNING:
                    return
                should_continue = _advance_step_locked(rec)
                if not should_continue:
                    rec.runner_task = None
                    return
    except asyncio.CancelledError:
        return


def _schedule_runner_locked(rec: SessionRecord) -> None:
    delay = get_step_delay_seconds()
    if delay <= 0:
        _advance_until_gate_or_done_locked(rec)
        return

    if rec.runner_task and not rec.runner_task.done():
        rec.runner_task.cancel()
    rec.runner_task = asyncio.create_task(_run_session_loop(rec.session_id, delay))


def build_session_response(rec: SessionRecord) -> DemoSessionResponse:
    can_pause = rec.status in (SessionStatus.RUNNING, SessionStatus.WAITING_FOR_HUMAN)
    can_resume = rec.status == SessionStatus.PAUSED
    can_cancel = rec.status in (
        SessionStatus.PLANNED,
        SessionStatus.RUNNING,
        SessionStatus.WAITING_FOR_HUMAN,
        SessionStatus.PAUSED,
    )
    can_decide = rec.status == SessionStatus.WAITING_FOR_HUMAN and rec.pending_approval is not None
    ordered_events = sorted(rec.events, key=lambda e: e.seq)

    return DemoSessionResponse(
        session_id=rec.session_id,
        status=rec.status,
        task=rec.task,
        scenario_id=rec.scenario_id,
        simulation_notice=SIMULATION_NOTICE,
        created_at=rec.created_at.isoformat(timespec="milliseconds"),
        updated_at=rec.updated_at.isoformat(timespec="milliseconds"),
        expires_at=rec.expires_at.isoformat(timespec="milliseconds"),
        ttl_remaining_seconds=session_store.ttl_remaining(rec),
        interaction_count=rec.interaction_count,
        max_interactions=get_max_interactions_per_session(),
        plan=rec.plan,
        pending_approval=rec.pending_approval,
        events=ordered_events,
        trust_summary=TrustSummary(
            planner_source=rec.plan.planner_source,
            planner_model=rec.plan.planner_model,
            calibration_label=rec.calibration_label,  # type: ignore[arg-type]
            calibration_dimensions=rec.calibration_dimensions,
            uncertainty_notes=rec.uncertainty_notes,
            what_rio_did=rec.what_rio_did,
            why_decisions_made=rec.why_decisions_made,
            evidence=rec.evidence,
            simulated_artifact=rec.simulated_artifact,
        ),
        controls=SessionControls(
            can_pause=can_pause,
            can_resume=can_resume,
            can_cancel=can_cancel,
            can_decide=can_decide,
        ),
    )


async def create_demo_session(task: str, scenario_id: Optional[str] = None) -> DemoSessionResponse:
    if scenario_id is not None and get_scenario_by_id(scenario_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown scenario_id '{scenario_id}'.",
        )

    clean_task = sanitize_text(task, max_len=300)
    draft = await generate_candidate_plan(clean_task, scenario_id=scenario_id)
    plan = apply_deterministic_policy(draft)

    now, expires_at = session_store.new_timestamps()
    session_id = generate_session_id()

    uncertainty_notes = [
        "All outputs operate strictly within the 3-document synthetic sandbox; external verification is not performed.",
        "Deterministic policy verification confirms rule & gate enforcement, NOT real-world factual accuracy of synthesized text.",
    ]
    if plan.planner_source == "deterministic_fallback":
        uncertainty_notes.append(
            f"Deterministic fallback planner active ({plan.fallback_reason or 'offline_mode'}); Groq LLM planning was bypassed or unavailable."
        )
    else:
        uncertainty_notes.append(
            "Plan structure was generated by Groq and independently constrained by R.I.O.'s deterministic policy allowlist."
        )

    why_decisions = [
        "PolicyEngine assigned deterministic risk tiers (low/medium/high) independently of the planner.",
        "High-risk output actions require explicit human approval before any downstream step executes.",
    ]
    if plan.boundary_triggered and plan.boundary_note:
        why_decisions.insert(0, f"SANDBOX_BOUNDARY_ENFORCED: {plan.boundary_note}")

    initial_calibration = CalibrationDimensions(
        policy_verification_status=(
            "boundary_enforced" if plan.boundary_triggered else "enforced_deterministic"
        ),
        policy_verification_note=(
            "Deterministic allowlist & gate policy evaluated before execution; rule compliance != factual truth."
        ),
        evidence_completeness_label=(
            "0 / 3 synthetic documents read yet"
            if not plan.boundary_triggered
            else "0 / 3 research documents needed (policy boundary audit only)"
        ),
        cited_document_ids=[],
        total_sandbox_documents=len(SANDBOX_DOCUMENTS),
        model_certainty_label=(
            "not_applicable_policy_only"
            if plan.boundary_triggered
            else "unvalidated_synthetic_synthesis"
        ),
        model_certainty_note=(
            "Boundary audit verifies allowlist constraints only."
            if plan.boundary_triggered
            else "Any synthesized comparison relies strictly on synthetic sandbox documents and is not empirically validated."
        ),
        execution_certainty_label="simulated_in_memory_only",
        execution_certainty_note="Execution occurs solely in ephemeral session memory; external I/O is disabled.",
    )

    rec = SessionRecord(
        session_id=session_id,
        status=SessionStatus.PLANNED,
        task=clean_task,
        scenario_id=scenario_id,
        created_at=now,
        updated_at=now,
        expires_at=expires_at,
        plan=plan,
        calibration_dimensions=initial_calibration,
        uncertainty_notes=uncertainty_notes,
        why_decisions_made=why_decisions,
    )

    _append_event(
        rec,
        event_type="session_created",
        status_str="planned",
        summary="Created ephemeral isolated demo session with 30-minute TTL.",
        metadata={"ttl_seconds": session_store.ttl_remaining(rec)},
    )
    _append_event(
        rec,
        event_type="plan_generated",
        status_str="planned",
        summary=f"Generated {len(plan.steps)}-step execution plan via {plan.planner_source}.",
        metadata={"planner_source": plan.planner_source, "step_count": len(plan.steps)},
    )
    _append_event(
        rec,
        event_type="policy_evaluated",
        status_str="planned",
        summary="Validated every action against deterministic sandbox allowlist and assigned risk gates.",
        policy_rule_id="DETERMINISTIC_ALLOWLIST_V1",
    )
    if plan.boundary_triggered:
        boundary_evt = _append_event(
            rec,
            event_type="policy_boundary_enforced",
            status_str="guarded",
            summary=plan.boundary_note or "Privileged operation blocked by public sandbox boundary.",
            risk=RiskLevel.HIGH,
            policy_rule_id="SANDBOX_BOUNDARY_ENFORCED",
        )
        rec.evidence.append(
            EvidenceRecord(
                evidence_id=generate_short_id("ev"),
                step_id="step_1",
                action_id=SandboxActionId.ANALYSE_TASK.value,
                event_id=boundary_evt.event_id,
                event_seq=boundary_evt.seq,
                policy_rule_id="SANDBOX_BOUNDARY_ENFORCED",
                document_ids=[],
                source="sandbox://policy/boundary-guard",
                verification_status="blocked_by_policy",
                certainty_kind="deterministic_policy_check",
                certainty_label="Boundary Guard Triggered (Boolean Rule)",
                excerpt=plan.boundary_note or "Blocked out-of-scope host/network request before planning.",
            )
        )

    session_store.create(rec)

    async with rec.lock:
        first_step = _find_next_ready_step(rec)
        if first_step is not None:
            _append_event(
                rec,
                event_type="execution_started",
                status_str="running",
                summary="Started sandbox execution engine.",
            )
            if first_step.requires_approval:
                _enter_waiting_for_approval(rec, first_step)
            else:
                first_step.status = StepStatus.RUNNING
                first_step.started_at = _iso_now()
                rec.status = SessionStatus.RUNNING
                _append_event(
                    rec,
                    event_type="step_started",
                    status_str="running",
                    summary=f"Executing '{first_step.title}': {first_step.description}",
                    step_id=first_step.step_id,
                    action_id=first_step.action_id.value,
                    risk=first_step.risk,
                    policy_rule_id=first_step.policy_rule_id,
                )
                _schedule_runner_locked(rec)

    return build_session_response(rec)


async def get_demo_session(session_id: str) -> DemoSessionResponse:
    rec = session_store.get(session_id)
    async with rec.lock:
        return build_session_response(rec)


def _check_interaction_budget(rec: SessionRecord) -> None:
    max_interactions = get_max_interactions_per_session()
    if rec.interaction_count >= max_interactions:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Per-session interaction cap ({max_interactions}) reached. Start a new session.",
        )
    rec.interaction_count += 1


async def submit_session_decision(
    session_id: str,
    payload: DecisionRequest,
) -> DemoSessionResponse:
    rec = session_store.get(session_id)
    async with rec.lock:
        _check_interaction_budget(rec)

        if rec.status == SessionStatus.PAUSED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Execution is currently paused. Resume the session before submitting an approval decision.",
            )

        if rec.status != SessionStatus.WAITING_FOR_HUMAN or rec.pending_approval is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"No pending human approval in current state '{rec.status.value}'.",
            )

        pending = rec.pending_approval
        if payload.action_id != pending.action_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Action '{payload.action_id.value}' is not currently awaiting approval "
                    f"(expected '{pending.action_id.value}')."
                ),
            )

        gated_step = next((s for s in rec.plan.steps if s.step_id == pending.step_id), None)
        if gated_step is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Pending approval step missing from execution plan.",
            )

        rec.pending_approval = None
        rec.updated_at = datetime.now(timezone.utc)

        if payload.decision == DecisionChoice.APPROVE:
            _append_event(
                rec,
                event_type="approval_granted",
                status_str="approved",
                summary=f"Visitor approved '{gated_step.action_id.value}'."
                + (f" Note: {payload.reason}" if payload.reason else ""),
                step_id=gated_step.step_id,
                action_id=gated_step.action_id.value,
                risk=gated_step.risk,
                policy_rule_id=gated_step.policy_rule_id,
                metadata={"reason": payload.reason} if payload.reason else {},
            )
            _apply_step_outputs_and_record_event(rec, gated_step)

            next_step = _find_next_ready_step(rec)
            if next_step is None:
                rec.status = SessionStatus.COMPLETED
                _append_event(
                    rec,
                    event_type="session_completed",
                    status_str="completed",
                    summary="All allowed sandbox workflow steps completed.",
                )
            elif next_step.requires_approval:
                _enter_waiting_for_approval(rec, next_step)
            else:
                next_step.status = StepStatus.RUNNING
                next_step.started_at = _iso_now()
                rec.status = SessionStatus.RUNNING
                _append_event(
                    rec,
                    event_type="step_started",
                    status_str="running",
                    summary=f"Executing '{next_step.title}': {next_step.description}",
                    step_id=next_step.step_id,
                    action_id=next_step.action_id.value,
                    risk=next_step.risk,
                    policy_rule_id=next_step.policy_rule_id,
                )
                _schedule_runner_locked(rec)

        else:
            # REJECT path: explicitly mark any pre-existing draft as unexported & rejected
            gated_step.status = StepStatus.REJECTED
            gated_step.completed_at = _iso_now()
            gated_step.output_summary = (
                "Export action rejected by human visitor; downstream completion skipped and external publication not performed."
            )
            rec.status = SessionStatus.REJECTED
            rec.calibration_label = "halted_by_human_rejection"

            rec.calibration_dimensions.policy_verification_status = "halted_by_human"
            rec.calibration_dimensions.policy_verification_note = (
                "Human rejection halted the workflow deterministically at the policy gate. "
                "This verifies gate enforcement, NOT output correctness."
            )
            rec.calibration_dimensions.model_certainty_label = "halted_before_export"
            rec.calibration_dimensions.model_certainty_note = (
                "Draft was held back prior to export; its synthesis remains unvalidated externally."
            )
            rec.calibration_dimensions.execution_certainty_label = "export_rejected_no_write"
            rec.calibration_dimensions.execution_certainty_note = (
                "Export action rejected; simulated export step skipped; external publication not performed."
            )

            if rec.simulated_artifact is not None:
                rec.simulated_artifact = SimulatedArtifact(
                    artifact_id=rec.simulated_artifact.artifact_id,
                    title="Unexported In-Memory Draft (Export Rejected)",
                    format=rec.simulated_artifact.format,
                    artifact_state="export_rejected_draft_only",
                    draft_created_in_memory=True,
                    export_approved=False,
                    external_publication_performed=False,
                    simulated_only=True,
                    notice=(
                        "EXPORT REJECTED: Draft generated in session memory only. "
                        "Export action rejected; external publication NOT performed."
                    ),
                    content=_build_comparison_markdown(
                        rec.task,
                        artifact_state="export_rejected_draft_only",
                        boundary_triggered=rec.plan.boundary_triggered,
                    ),
                    citations=list(rec.simulated_artifact.citations),
                )

            rec.what_rio_did.append(
                f"Halted execution immediately when visitor rejected high-risk action '{gated_step.action_id.value}'."
            )
            rec.why_decisions_made.append(
                f"Human rejection blocked '{gated_step.action_id.value}'; draft remains unpublished in session memory and dependent final steps were skipped."
            )

            rejected_evt = _append_event(
                rec,
                event_type="approval_rejected",
                status_str="rejected",
                summary=f"Visitor rejected '{gated_step.action_id.value}'. Execution safely halted.",
                step_id=gated_step.step_id,
                action_id=gated_step.action_id.value,
                risk=gated_step.risk,
                policy_rule_id=gated_step.policy_rule_id,
                metadata={"reason": payload.reason} if payload.reason else {},
            )
            rec.evidence.append(
                EvidenceRecord(
                    evidence_id=generate_short_id("ev"),
                    step_id=gated_step.step_id,
                    action_id=gated_step.action_id.value,
                    event_id=rejected_evt.event_id,
                    event_seq=rejected_evt.seq,
                    policy_rule_id=gated_step.policy_rule_id,
                    document_ids=list(rec.calibration_dimensions.cited_document_ids),
                    source="human://visitor-approval-gate",
                    verification_status="rejected_by_human",
                    certainty_kind="human_decision_record",
                    certainty_label="Human Gate Rejected (Export Blocked)",
                    excerpt=(
                        f"Visitor rejected '{gated_step.action_id.value}'; external publication not performed."
                        + (f" Rationale: {payload.reason}" if payload.reason else "")
                    ),
                )
            )

            for step in rec.plan.steps:
                if step.status == StepStatus.PENDING:
                    step.status = StepStatus.SKIPPED
                    step.output_summary = (
                        f"Skipped because prerequisite gate '{gated_step.action_id.value}' was rejected."
                    )
                    _append_event(
                        rec,
                        event_type="step_skipped",
                        status_str="skipped",
                        summary=step.output_summary,
                        step_id=step.step_id,
                        action_id=step.action_id.value,
                        risk=step.risk,
                        policy_rule_id=step.policy_rule_id,
                    )

        return build_session_response(rec)


async def submit_session_interrupt(
    session_id: str,
    payload: InterruptRequest,
) -> DemoSessionResponse:
    rec = session_store.get(session_id)
    async with rec.lock:
        _check_interaction_budget(rec)
        cmd = payload.command
        rec.updated_at = datetime.now(timezone.utc)

        if cmd == InterruptCommand.PAUSE:
            if rec.status not in (SessionStatus.RUNNING, SessionStatus.WAITING_FOR_HUMAN):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot pause session in state '{rec.status.value}'.",
                )
            if rec.runner_task and not rec.runner_task.done():
                rec.runner_task.cancel()
            rec.runner_task = None
            rec.paused_from_status = rec.status
            rec.status = SessionStatus.PAUSED
            for step in rec.plan.steps:
                if step.status == StepStatus.RUNNING:
                    step.status = StepStatus.PAUSED

            rec.why_decisions_made.append("Visitor invoked PAUSE; active execution suspended cleanly.")
            _append_event(
                rec,
                event_type="execution_paused",
                status_str="paused",
                summary="Execution paused by visitor control."
                + (f" Note: {payload.reason}" if payload.reason else ""),
                metadata={"paused_from": rec.paused_from_status.value},
            )

        elif cmd == InterruptCommand.RESUME:
            if rec.status != SessionStatus.PAUSED:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot resume session in state '{rec.status.value}'.",
                )
            previous = rec.paused_from_status or SessionStatus.RUNNING
            rec.paused_from_status = None

            if previous == SessionStatus.WAITING_FOR_HUMAN and rec.pending_approval is not None:
                rec.status = SessionStatus.WAITING_FOR_HUMAN
                _append_event(
                    rec,
                    event_type="execution_resumed",
                    status_str="waiting_for_human",
                    summary=f"Resumed session; still awaiting approval for '{rec.pending_approval.action_id.value}'.",
                )
            else:
                rec.status = SessionStatus.RUNNING
                for step in rec.plan.steps:
                    if step.status == StepStatus.PAUSED:
                        step.status = StepStatus.RUNNING
                _append_event(
                    rec,
                    event_type="execution_resumed",
                    status_str="running",
                    summary="Resumed sandbox step execution.",
                )
                _schedule_runner_locked(rec)

        elif cmd == InterruptCommand.CANCEL:
            if rec.status in (
                SessionStatus.COMPLETED,
                SessionStatus.REJECTED,
                SessionStatus.CANCELLED,
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Session is already in terminal state '{rec.status.value}'.",
                )

            if rec.runner_task and not rec.runner_task.done():
                rec.runner_task.cancel()
            rec.runner_task = None
            rec.paused_from_status = None
            rec.pending_approval = None
            rec.status = SessionStatus.CANCELLED
            rec.calibration_label = "cancelled_by_visitor"
            rec.calibration_dimensions.execution_certainty_label = "cancelled_no_write"
            rec.calibration_dimensions.execution_certainty_note = (
                "Task cancelled by visitor control; no simulated export or external publication occurred."
            )

            if rec.simulated_artifact is not None:
                rec.simulated_artifact = SimulatedArtifact(
                    artifact_id=rec.simulated_artifact.artifact_id,
                    title="Unexported In-Memory Draft (Task Cancelled)",
                    format=rec.simulated_artifact.format,
                    artifact_state="cancelled_draft_only",
                    draft_created_in_memory=True,
                    export_approved=False,
                    external_publication_performed=False,
                    simulated_only=True,
                    notice=(
                        "TASK CANCELLED: Draft held in session memory only; export did not run and external publication was NOT performed."
                    ),
                    content=_build_comparison_markdown(
                        rec.task,
                        artifact_state="cancelled_draft_only",
                        boundary_triggered=rec.plan.boundary_triggered,
                    ),
                    citations=list(rec.simulated_artifact.citations),
                )

            for step in rec.plan.steps:
                if step.status in (
                    StepStatus.RUNNING,
                    StepStatus.PAUSED,
                    StepStatus.WAITING_FOR_HUMAN,
                ):
                    step.status = StepStatus.CANCELLED
                    step.completed_at = _iso_now()
                    step.output_summary = "Cancelled by visitor intervention."
                elif step.status == StepStatus.PENDING:
                    step.status = StepStatus.SKIPPED
                    step.output_summary = "Skipped because session was cancelled."

            rec.what_rio_did.append("Aborted remaining workflow immediately upon visitor CANCEL command.")
            rec.why_decisions_made.append(
                "Visitor cancelled execution; remaining simulated actions were aborted and skipped."
            )
            _append_event(
                rec,
                event_type="execution_cancelled",
                status_str="cancelled",
                summary="Task cancelled by visitor control. No further actions will run."
                + (f" Note: {payload.reason}" if payload.reason else ""),
            )

        return build_session_response(rec)
