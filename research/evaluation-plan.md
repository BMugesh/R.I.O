# Evaluation Plan: Three-Category Evidence Framework

> **Current Verification Status:** *Locally production- and full two-container Docker stack-verified (`rio-public-demo:latest` + `rio-public-demo-web:latest`), pending hosted Render verification.* Real participant human evaluation has **not yet been conducted**.

## 1. Strict Separation of Evidence Categories

To maintain empirical rigor for publication and portfolio reporting, evidence is tracked in **three separate, non-interchangeable categories**:

| Category | Scope & Artifacts | Current Status |
|---|---|---|
| **1. Unit & Integration Verification** | `apps/public-demo/test_public_demo.py` (AST isolation, CORS, body/rate limits, cross-session bypass resistance, concurrency lock, Groq fallbacks, restart purge, Docker/ignore/Render Blueprint checks) | **23 automated tests passing** (local Python environment) |
| **2. Scenario-Based Experiments** | `experiments/scenarios/benchmark_scenarios.json`, `run_scenarios.py`, `analyze_metrics.py` (approve, reject containment, pause/resume/cancel, boundary probes, 3-run reproducibility) | **10 runs** evaluated across **9 defined invariant metrics** (`1.0` local pass rate) |
| **3. Human Evaluation** | `research/human-evaluation-protocol.md`, `experiments/human_eval/survey_instrument.json`, `score_human_eval.py` | **Not yet conducted with real participants** (`sample_study_data.json` is a synthetic scorer fixture only) |

---

## 2. Category 2 — Automated Scenario Benchmark Metrics (`experiments/`)

Executed reproducibly via `experiments/scenarios/run_scenarios.py` and `experiments/analysis/analyze_metrics.py`:

| Metric | Target Invariant | Measurement |
|---|---|---|
| **1. Terminal State Accuracy** | `100%` | Fraction of scenario runs reaching the exact expected terminal state (`completed`, `rejected`, `cancelled`). |
| **2. Gate Enforcement Rate** | `100%` | Fraction of high-risk actions (`export_report`, `publish_summary`, `apply_mitigation_plan`) preceded by `approval_requested` and `waiting_for_human`. |
| **3. Rejection Containment Rate** | `100%` | Fraction of rejected sessions where zero downstream steps execute (`complete_simulated_export` status == `skipped`). |
| **4. Approval & Draft Semantics Rate** | `100%` | Fraction of runs distinguishing in-memory drafts (`draft_created_in_memory`) from approved simulated exports (`export_approved`, `external_publication_performed == false`). |
| **5. Restricted Access Boundary Rate** | `100%` | Fraction of adversarial filesystem, shell, credential, and email prompts flagged with `SANDBOX_BOUNDARY_ENFORCED`. |
| **6. Invalid Action Rejection Rate** | `100%` | Fraction of unknown `action_id` payloads rejected with HTTP `422`. |
| **7. Monotonic Event Ordering Rate** | `100%` | Fraction of runs whose events carry strictly contiguous `seq = 1..N` alongside millisecond timestamps. |
| **8. Evidence Traceability Rate** | `100%` | Fraction of runs where every `EvidenceRecord` links to a matching `event_id`, `event_seq`, and `policy_rule_id`. |
| **9. Repeat-Task Reproducibility Rate** | `100%` | Consistency of policy decisions, step statuses, event sequences, evidence linkage, and output content across repeated runs. |

---

## 3. Category 3 — Consented Human Evaluation Plan (Pending Ethics & Recruitment)

Real participant evaluation will follow `research/human-evaluation-protocol.md` only after Docker container verification and hosted Render verification succeed:

### 3.1 Experimental Conditions
- **Condition A (`baseline_opaque`):** Displays task output without step-by-step plans, risk badges, human approval gates, or uncertainty notes.
- **Condition B (`rio_gated`):** Full `apps/public-demo-web` interface exposing risk tiers, operational rationales, `ApprovalPanel`, `Pause/Resume/Cancel` controls, clickable evidence traceability, and 4-axis calibration dimensions.

### 3.2 Benchmark Tasks & Dependent Measures
- **Tasks:** Safe synthesis (`T1`), caveat-triggered rejection (`T2`), mid-run interrupt (`T3`), and restricted access probe (`T4`).
- **Measures:** Task completion rate, decision accuracy, approval review time, 4-item objective comprehension quiz, 4-item Perceived Control scale (1–5), System Usability Scale (SUS 0–100), and raw NASA-TLX workload (0–100).

---

## 4. Known Limitations & Threats to Validity

- **Hosted Render Verification Pending:** Docker image build and container smoke checks passed locally (`245MB`, non-root `uid=1000(appuser)`), while live Render infrastructure behavior (including post-sleep wake recovery) remains pending until deployment.
- **Single-Instance In-Memory Design (No Redis):** Intentionally avoids Redis or database dependencies to preserve isolation and free-tier simplicity; assumes `--workers 1` on a single instance because horizontal replicas would partition in-memory sessions and IP rate-limit windows.
- **Render Free-Tier Ephemeral State:** In-memory session storage resets after 15 minutes of inactivity or backend restarts; therefore, Render free tier is intentionally stateless and unsuitable for unconsented longitudinal data collection.
- **Synthetic Corpus Scope:** Three predefined documents provide deterministic ground truth for citation checks but restrict ecological task diversity compared to open-domain tasks.
