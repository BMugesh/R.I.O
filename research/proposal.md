# Research Proposal: Human-Gated Transparency and Calibrated Trust in Autonomous AI Orchestration (R.I.O.)

## 1. Problem Statement

Modern agentic AI systems increasingly compose multi-step tool workflows across documents, APIs, and local operating systems. Two failure modes limit safe real-world adoption:

1. **Unconstrained Tool Authority:** When a large language model (LLM) generates both the task plan and executable tool permissions, prompt injections or hallucinations can trigger destructive, unapproved, or out-of-scope operations.
2. **Opaque & Overconfident Interfaces:** Most conversational agent UIs hide intermediate reasoning summaries, risk classifications, and source caveats, encouraging blind over-reliance when outputs appear fluent despite narrow evidence grounding.

R.I.O. (Reasoning Intelligence Orchestration) addresses these challenges by separating **probabilistic task planning** from **deterministic safety policy enforcement**, pausing execution at explicit human approval gates, and exposing calibrated uncertainty alongside verifiable execution evidence.

## 2. Research Objectives & Hypotheses

This research investigates how an interactive, human-gated orchestration interface affects user safety, intervention accuracy, and trust calibration:

- **H1 (Transparency):** Surfacing step-by-step operational summaries, policy rule identifiers, and source citations enables visitors to identify unsupported claims or inappropriate scope before approving high-risk actions.
- **H2 (Human Control):** Providing real-time intervention controls (`approve`, `reject`, `pause`, `resume`, `cancel`) backed by hard execution gates reduces unsafe downstream completion rates to zero on rejected workflows without rendering normal execution unusable.
- **H3 (Calibrated Trust):** Separating four orthogonal trust dimensions (`CalibrationDimensions`: policy verification status, evidence completeness against synthetic sources, model output certainty, and execution certainty alongside explicit `uncertainty_notes` and document caveats) reduces blind over-reliance compared to ambiguous percentage scores or opaque "all-green" completion indicators.

## 3. Architectural Isolation: Private Runtime vs. Public Research Sandbox

To study visitor interactions safely on the open web without exposing personal data, local files, desktop automation, Android device bridges, or MCP tool integrations, the repository enforces a strict architectural boundary:

| Layer | Private Local R.I.O. (`apps/api`, `apps/web`, `runtime/`) | Public Research Sandbox (`apps/public-demo`, `apps/public-demo-web`) |
|---|---|---|
| **Exposure** | Localhost / private LAN only | Publicly accessible Render static site + isolated FastAPI container |
| **Capabilities** | 14 local agents, filesystem, desktop, devices, MCP, Qiskit | Strict 12-action read/synthesis/audit/simulated-export allowlist |
| **Data Scope** | Personal context, PostgreSQL/pgvector, Redis | 3 fixed synthetic research documents (`DOC-01`..`DOC-03`), ephemeral 30-min RAM |
| **LLM Authority** | Capability-routed model execution | Optional Groq planning *only*; deterministic `PolicyEngine` owns permissions |
| **Persistence** | Long-term memory store | No persistent storage of visitor task text by default |

## 4. Ethics & Data Minimization

Because the public demonstration requires no login and is open to arbitrary internet visitors:
- Visitor prompts are bounded to 300 characters and stored exclusively in ephemeral in-memory sessions with a 30-minute TTL (`SESSION_TTL_SECONDS=1800`).
- No visitor prompt text or PII is written to disk or external analytics pipelines in the public demo deployment.
- Any formal human-subject study using recorded telemetry must occur under explicit informed consent in controlled evaluation sessions (see `research/evaluation-plan.md`).
