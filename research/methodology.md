# Methodology: Decoupled Planning, Deterministic Policy Enforcement, and Event Instrumentation

## 1. System Design

The public R.I.O. research demonstrator (`apps/public-demo` + `apps/public-demo-web`) implements a five-stage pipeline designed for reproducibility and verifiable safety invariants:

### 1.1 Constrained Candidate Planning (`planner.py`)
- Accepts a sanitized visitor task (`3 <= len <= 300` characters) and optional `scenario_id`.
- Runs an upfront lexical boundary check (`detect_sandbox_boundary_trigger`) that flags privileged local, shell, credential, or external network requests before any LLM call.
- When `GROQ_API_KEY` is configured server-side, sends a bounded request (`timeout=12s`, `max_tokens=700`, `temperature=0.2`, JSON object response format) asking Groq to propose 2–6 steps strictly using the 12 enum values of `SandboxActionId`.
- Strips any `<think>...</think>` private chain-of-thought blocks and validates the JSON payload via Pydantic (`GroqPlanPayload`). Any network failure, quota error (`429`), timeout, malformed JSON, or unallowlisted `action_id` triggers an automatic fallback to `build_deterministic_plan`.

### 1.2 Deterministic Policy Engine (`engine.py`)
Groq never decides permissions or risk tiers. `apply_deterministic_policy()` maps every `SandboxActionId` through `POLICY_CATALOG`:
- **Low Risk (`requires_approval=False`):** `analyse_task`, `read_sample_documents`, `inspect_sandbox_dataset`, `verify_citations`, `run_policy_audit`, `complete_simulated_export`.
- **Medium Risk (`requires_approval=False`):** `extract_key_claims`, `generate_comparison`, `draft_briefing`.
- **High Risk (`requires_approval=True`):** `export_report`, `publish_summary`, `apply_mitigation_plan` (`HUMAN_APPROVAL_REQUIRED`).

Dependencies are normalized into a strict forward DAG (`dep_idx < current_idx`), and any `complete_simulated_export` step is forcibly wired to depend on the gated high-risk step so rejecting a gate strictly blocks downstream recording.

### 1.3 Finite-State Execution & Intervention Machine
Sessions transition deterministically across seven states (`planned`, `running`, `waiting_for_human`, `paused`, `completed`, `rejected`, `cancelled`):
- **Step progression:** Non-gated steps advance sequentially under a per-session `asyncio.Lock`.
- **Approval gate:** Reaching a `requires_approval=True` step halts progression in `waiting_for_human` and emits `approval_requested`.
- **Approve (`POST /decision`):** Emits `approval_granted`, records verified human evidence, unlocks downstream execution, and completes in `completed`.
- **Reject (`POST /decision`):** Emits `approval_rejected`, marks the gated step `rejected`, marks dependent downstream steps `skipped`, sets calibration label `halted_by_human`, and halts in `rejected`.
- **Interrupts (`POST /interrupt`):** `pause` freezes active execution (preserving `paused_from_status` even during `waiting_for_human`, blocking decisions until `resume`); `cancel` immediately terminates active and pending steps into `cancelled`/`skipped`.

## 2. Trust Calibration, Draft Semantics & Evidence Traceability

Rather than displaying ambiguous percentage confidence scores (e.g., conflating a deterministic rule check passing with real-world output correctness), `TrustSummary` separates four orthogonal dimensions inside `CalibrationDimensions`:
- **Policy Verification (`policy_verification_status`):** Confirms deterministic allowlist and gate rule enforcement (`enforced_deterministic`, `halted_by_human`, or `boundary_enforced`) — explicitly stating that rule compliance does not prove factual output truth.
- **Evidence Grounding (`evidence_completeness_label` & `cited_document_ids`):** Tracks exact coverage against the 3 synthetic sandbox documents (`DOC-01`–`DOC-03`) vs. zero external sources.
- **Model Output Certainty (`model_certainty_label`):** Marks generated syntheses as `unvalidated_synthetic_synthesis`, `not_applicable_policy_only`, or `halted_before_export`.
- **Execution Certainty (`execution_certainty_label`):** Separates `simulated_in_memory_only`, `export_rejected_no_write`, and `cancelled_no_write`.

Similarly, `SimulatedArtifact` separates draft generation from export authorization (`draft_created_in_memory`, `export_approved`, `external_publication_performed`, and `artifact_state`), ensuring a rejected export never appears completed.

## 3. Research Instrumentation & Event-Evidence Traceability

Every `ExecutionEvent` carries a strictly monotonic 1-based sequence number (`seq`), a unique `event_id`, and a millisecond-precision UTC timestamp (`timespec="milliseconds"`), preserving exact ordering even when multiple events emit within the same second. Every `EvidenceRecord` links directly to its generating `event_id`, `event_seq`, `policy_rule_id`, and referenced `document_ids` (`experiments/metrics/telemetry_schema.json`).
