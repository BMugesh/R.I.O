export type RiskLevel = 'low' | 'medium' | 'high';

export type StepStatus =
  | 'pending'
  | 'running'
  | 'waiting_for_human'
  | 'paused'
  | 'completed'
  | 'rejected'
  | 'skipped'
  | 'cancelled';

export type SessionStatus =
  | 'planned'
  | 'running'
  | 'waiting_for_human'
  | 'paused'
  | 'completed'
  | 'rejected'
  | 'cancelled';

export type DecisionChoice = 'approve' | 'reject';
export type InterruptCommand = 'pause' | 'resume' | 'cancel';

export interface SandboxDocument {
  doc_id: string;
  title: string;
  domain: string;
  date: string;
  summary: string;
  key_metrics: Record<string, string>;
  caveats: string;
}

export interface ScenarioSummary {
  id: string;
  title: string;
  description: string;
  task: string;
  category: string;
  expected_risk_peak: RiskLevel;
  has_approval_gate: boolean;
  gated_action_id?: string | null;
}

export interface AllowedActionInfo {
  action_id: string;
  label: string;
  risk: RiskLevel;
  requires_approval: boolean;
  policy_rule_id: string;
  sandbox_target: string;
}

export interface ScenariosResponse {
  scenarios: ScenarioSummary[];
  sandbox_documents: SandboxDocument[];
  allowed_actions: AllowedActionInfo[];
  simulation_notice: string;
}

export interface PlanStep {
  step_id: string;
  order: number;
  action_id: string;
  title: string;
  description: string;
  reasoning_summary: string;
  depends_on: string[];
  risk: RiskLevel;
  requires_approval: boolean;
  policy_rule_id: string;
  sandbox_target: string;
  status: StepStatus;
  started_at?: string | null;
  completed_at?: string | null;
  output_summary?: string | null;
}

export interface ExecutionPlan {
  plan_id: string;
  goal_summary: string;
  planner_source: 'groq_assisted' | 'deterministic_fallback';
  planner_model?: string | null;
  fallback_reason?: string | null;
  boundary_triggered: boolean;
  boundary_note?: string | null;
  steps: PlanStep[];
}

export interface PendingApproval {
  approval_id: string;
  step_id: string;
  action_id: string;
  title: string;
  description: string;
  risk: RiskLevel;
  policy_rule_id: string;
  sandbox_target: string;
  if_approved: string;
  if_rejected: string;
  requested_at: string;
}

export interface ExecutionEvent {
  seq: number;
  event_id: string;
  timestamp: string;
  event_type: string;
  step_id?: string | null;
  action_id?: string | null;
  risk?: RiskLevel | null;
  policy_rule_id?: string | null;
  status: string;
  summary: string;
  metadata: Record<string, unknown>;
}

export interface EvidenceRecord {
  evidence_id: string;
  step_id: string;
  action_id: string;
  event_id: string;
  event_seq: number;
  policy_rule_id: string;
  document_ids: string[];
  source: string;
  verification_status:
    | 'verified_rule'
    | 'synthetic_source'
    | 'unvalidated_draft'
    | 'rejected_by_human'
    | 'blocked_by_policy';
  certainty_kind:
    | 'deterministic_policy_check'
    | 'synthetic_corpus_read'
    | 'heuristic_synthesis'
    | 'human_decision_record';
  certainty_label: string;
  excerpt: string;
}

export interface SimulatedArtifact {
  artifact_id: string;
  title: string;
  format: string;
  artifact_state:
    | 'draft_pending_approval'
    | 'export_approved_simulated'
    | 'export_rejected_draft_only'
    | 'cancelled_draft_only';
  draft_created_in_memory: boolean;
  export_approved: boolean;
  external_publication_performed: boolean;
  simulated_only: boolean;
  notice: string;
  content: string;
  citations: string[];
}

export interface CalibrationDimensions {
  policy_verification_status:
    | 'enforced_deterministic'
    | 'halted_by_human'
    | 'boundary_enforced';
  policy_verification_note: string;
  evidence_completeness_label: string;
  cited_document_ids: string[];
  total_sandbox_documents: number;
  model_certainty_label:
    | 'unvalidated_synthetic_synthesis'
    | 'not_applicable_policy_only'
    | 'halted_before_export';
  model_certainty_note: string;
  execution_certainty_label:
    | 'simulated_in_memory_only'
    | 'export_rejected_no_write'
    | 'cancelled_no_write';
  execution_certainty_note: string;
}

export interface TrustSummary {
  planner_source: 'groq_assisted' | 'deterministic_fallback';
  planner_model?: string | null;
  policy_engine: string;
  calibration_label:
    | 'policy_enforced_unvalidated_output'
    | 'policy_and_corpus_grounded'
    | 'halted_by_human_rejection'
    | 'cancelled_by_visitor';
  calibration_dimensions: CalibrationDimensions;
  uncertainty_notes: string[];
  what_rio_did: string[];
  why_decisions_made: string[];
  evidence: EvidenceRecord[];
  simulated_artifact?: SimulatedArtifact | null;
}

export interface SessionControls {
  can_pause: boolean;
  can_resume: boolean;
  can_cancel: boolean;
  can_decide: boolean;
}

export interface DemoSessionResponse {
  session_id: string;
  status: SessionStatus;
  task: string;
  scenario_id?: string | null;
  execution_mode: 'isolated_sandbox';
  simulation_notice: string;
  created_at: string;
  updated_at: string;
  expires_at: string;
  ttl_remaining_seconds: number;
  interaction_count: number;
  max_interactions: number;
  plan: ExecutionPlan;
  pending_approval?: PendingApproval | null;
  events: ExecutionEvent[];
  trust_summary: TrustSummary;
  controls: SessionControls;
}

export interface HealthResponse {
  status: string;
  service: string;
  mode: string;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function normalizeApiBaseUrl(raw?: string): string {
  const trimmed = (raw ?? '').trim().replace(/\/+$/, '');
  if (!trimmed) {
    return 'http://localhost:8000';
  }
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed;
  }
  const scheme = /^(localhost|127\.0\.0\.1)(:|\/|$)/i.test(trimmed) ? 'http' : 'https';
  return `${scheme}://${trimmed}`;
}

export const API_BASE_URL = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL);

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  });

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      if (typeof data?.detail === 'string') {
        detail = data.detail;
      } else if (Array.isArray(data?.detail) && data.detail[0]?.msg) {
        detail = data.detail[0].msg;
      }
    } catch {
      // Ignore parse failures on non-JSON error responses
    }
    throw new ApiError(response.status, detail);
  }

  return response.json() as Promise<T>;
}

export function checkHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return requestJson<HealthResponse>('/health', { signal });
}

export function fetchScenarios(signal?: AbortSignal): Promise<ScenariosResponse> {
  return requestJson<ScenariosResponse>('/api/demo/scenarios', { signal });
}

export function createSession(
  task: string,
  scenarioId?: string | null
): Promise<DemoSessionResponse> {
  return requestJson<DemoSessionResponse>('/api/demo/sessions', {
    method: 'POST',
    body: JSON.stringify({
      task,
      scenario_id: scenarioId ?? null,
    }),
  });
}

export function fetchSession(sessionId: string): Promise<DemoSessionResponse> {
  return requestJson<DemoSessionResponse>(
    `/api/demo/sessions/${encodeURIComponent(sessionId)}`
  );
}

export function submitDecision(
  sessionId: string,
  actionId: string,
  decision: DecisionChoice,
  reason?: string
): Promise<DemoSessionResponse> {
  return requestJson<DemoSessionResponse>(
    `/api/demo/sessions/${encodeURIComponent(sessionId)}/decision`,
    {
      method: 'POST',
      body: JSON.stringify({
        action_id: actionId,
        decision,
        reason: reason?.trim() ? reason.trim() : null,
      }),
    }
  );
}

export function submitInterrupt(
  sessionId: string,
  command: InterruptCommand,
  reason?: string
): Promise<DemoSessionResponse> {
  return requestJson<DemoSessionResponse>(
    `/api/demo/sessions/${encodeURIComponent(sessionId)}/interrupt`,
    {
      method: 'POST',
      body: JSON.stringify({
        command,
        reason: reason?.trim() ? reason.trim() : null,
      }),
    }
  );
}
