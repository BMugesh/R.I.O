"""Strict Pydantic schemas for the isolated R.I.O. public demonstration API."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_HUMAN = "waiting_for_human"
    PAUSED = "paused"
    COMPLETED = "completed"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class SessionStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    WAITING_FOR_HUMAN = "waiting_for_human"
    PAUSED = "paused"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class DecisionChoice(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class InterruptCommand(str, Enum):
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"


class SandboxActionId(str, Enum):
    """Strict allowlist of deterministic sandbox operations."""

    ANALYSE_TASK = "analyse_task"
    READ_SAMPLE_DOCUMENTS = "read_sample_documents"
    INSPECT_SANDBOX_DATASET = "inspect_sandbox_dataset"
    EXTRACT_KEY_CLAIMS = "extract_key_claims"
    VERIFY_CITATIONS = "verify_citations"
    GENERATE_COMPARISON = "generate_comparison"
    DRAFT_BRIEFING = "draft_briefing"
    RUN_POLICY_AUDIT = "run_policy_audit"
    EXPORT_REPORT = "export_report"
    PUBLISH_SUMMARY = "publish_summary"
    APPLY_MITIGATION_PLAN = "apply_mitigation_plan"
    COMPLETE_SIMULATED_EXPORT = "complete_simulated_export"


class SandboxDocument(BaseModel):
    doc_id: str
    title: str
    domain: str
    date: str
    summary: str
    key_metrics: Dict[str, str]
    caveats: str


class ScenarioSummary(BaseModel):
    id: str
    title: str
    description: str
    task: str
    category: str
    expected_risk_peak: RiskLevel
    has_approval_gate: bool
    gated_action_id: Optional[SandboxActionId] = None


class AllowedActionInfo(BaseModel):
    action_id: SandboxActionId
    label: str
    risk: RiskLevel
    requires_approval: bool
    policy_rule_id: str
    sandbox_target: str


class ScenariosResponse(BaseModel):
    scenarios: List[ScenarioSummary]
    sandbox_documents: List[SandboxDocument]
    allowed_actions: List[AllowedActionInfo]
    simulation_notice: str


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: str = Field(..., min_length=3, max_length=300)
    scenario_id: Optional[str] = Field(default=None, max_length=64)

    @field_validator("task")
    @classmethod
    def validate_and_clean_task(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if len(cleaned) < 3:
            raise ValueError("Task must contain at least 3 non-whitespace characters.")
        if len(cleaned) > 300:
            raise ValueError("Task must be 300 characters or fewer.")
        return cleaned

    @field_validator("scenario_id")
    @classmethod
    def clean_scenario_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: SandboxActionId
    decision: DecisionChoice
    reason: Optional[str] = Field(default=None, max_length=200)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        return cleaned or None


class InterruptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: InterruptCommand
    reason: Optional[str] = Field(default=None, max_length=200)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        return cleaned or None


class PlanStep(BaseModel):
    step_id: str
    order: int
    action_id: SandboxActionId
    title: str
    description: str
    reasoning_summary: str
    depends_on: List[str] = Field(default_factory=list)
    risk: RiskLevel
    requires_approval: bool
    policy_rule_id: str
    sandbox_target: str
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    output_summary: Optional[str] = None


class ExecutionPlan(BaseModel):
    plan_id: str
    goal_summary: str
    planner_source: Literal["groq_assisted", "deterministic_fallback"]
    planner_model: Optional[str] = None
    fallback_reason: Optional[str] = None
    boundary_triggered: bool = False
    boundary_note: Optional[str] = None
    steps: List[PlanStep]


class PendingApproval(BaseModel):
    approval_id: str
    step_id: str
    action_id: SandboxActionId
    title: str
    description: str
    risk: RiskLevel
    policy_rule_id: str
    sandbox_target: str
    if_approved: str
    if_rejected: str
    requested_at: str


class ExecutionEvent(BaseModel):
    seq: int = Field(..., ge=1)
    event_id: str
    timestamp: str
    event_type: str
    step_id: Optional[str] = None
    action_id: Optional[str] = None
    risk: Optional[RiskLevel] = None
    policy_rule_id: Optional[str] = None
    status: str
    summary: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvidenceRecord(BaseModel):
    evidence_id: str
    step_id: str
    action_id: str
    event_id: str
    event_seq: int = Field(..., ge=1)
    policy_rule_id: str
    document_ids: List[str] = Field(default_factory=list)
    source: str
    verification_status: Literal[
        "verified_rule",
        "synthetic_source",
        "unvalidated_draft",
        "rejected_by_human",
        "blocked_by_policy",
    ]
    certainty_kind: Literal[
        "deterministic_policy_check",
        "synthetic_corpus_read",
        "heuristic_synthesis",
        "human_decision_record",
    ]
    certainty_label: str
    excerpt: str


class SimulatedArtifact(BaseModel):
    artifact_id: str
    title: str
    format: str = "markdown_report"
    artifact_state: Literal[
        "draft_pending_approval",
        "export_approved_simulated",
        "export_rejected_draft_only",
        "cancelled_draft_only",
    ]
    draft_created_in_memory: bool = True
    export_approved: bool = False
    external_publication_performed: bool = False
    simulated_only: bool = True
    notice: str
    content: str
    citations: List[str]


class CalibrationDimensions(BaseModel):
    policy_verification_status: Literal[
        "enforced_deterministic",
        "halted_by_human",
        "boundary_enforced",
    ]
    policy_verification_note: str
    evidence_completeness_label: str
    cited_document_ids: List[str]
    total_sandbox_documents: int
    model_certainty_label: Literal[
        "unvalidated_synthetic_synthesis",
        "not_applicable_policy_only",
        "halted_before_export",
    ]
    model_certainty_note: str
    execution_certainty_label: Literal[
        "simulated_in_memory_only",
        "export_rejected_no_write",
        "cancelled_no_write",
    ]
    execution_certainty_note: str


class TrustSummary(BaseModel):
    planner_source: Literal["groq_assisted", "deterministic_fallback"]
    planner_model: Optional[str] = None
    policy_engine: str = "deterministic_allowlist_v1"
    calibration_label: Literal[
        "policy_enforced_unvalidated_output",
        "policy_and_corpus_grounded",
        "halted_by_human_rejection",
        "cancelled_by_visitor",
    ]
    calibration_dimensions: CalibrationDimensions
    uncertainty_notes: List[str]
    what_rio_did: List[str]
    why_decisions_made: List[str]
    evidence: List[EvidenceRecord]
    simulated_artifact: Optional[SimulatedArtifact] = None


class SessionControls(BaseModel):
    can_pause: bool
    can_resume: bool
    can_cancel: bool
    can_decide: bool


class DemoSessionResponse(BaseModel):
    session_id: str
    status: SessionStatus
    task: str
    scenario_id: Optional[str] = None
    execution_mode: Literal["isolated_sandbox"] = "isolated_sandbox"
    simulation_notice: str
    created_at: str
    updated_at: str
    expires_at: str
    ttl_remaining_seconds: int
    interaction_count: int
    max_interactions: int
    plan: ExecutionPlan
    pending_approval: Optional[PendingApproval] = None
    events: List[ExecutionEvent]
    trust_summary: TrustSummary
    controls: SessionControls
