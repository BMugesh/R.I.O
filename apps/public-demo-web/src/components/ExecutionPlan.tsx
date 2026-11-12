import React from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  GitBranch,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  ShieldAlert,
  Slash,
  XCircle,
} from 'lucide-react';
import type { DemoSessionResponse, InterruptCommand, PlanStep, StepStatus } from '../api';

interface ExecutionPlanProps {
  session: DemoSessionResponse;
  isBusy: boolean;
  onInterrupt: (command: InterruptCommand) => Promise<void>;
  onRefresh: () => Promise<void>;
}

function formatTtl(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}m ${String(secs).padStart(2, '0')}s`;
}

function renderStepIcon(status: StepStatus) {
  switch (status) {
    case 'running':
      return <Loader2 size={16} className="spin" color="#22d3ee" />;
    case 'waiting_for_human':
      return <ShieldAlert size={16} color="#fbbf24" />;
    case 'completed':
      return <CheckCircle2 size={16} color="#34d399" />;
    case 'rejected':
      return <XCircle size={16} color="#fb7185" />;
    case 'paused':
      return <Pause size={16} color="#fbbf24" />;
    case 'cancelled':
    case 'skipped':
      return <Slash size={16} color="#64748b" />;
    default:
      return <Clock size={16} color="#64748b" />;
  }
}

export const ExecutionPlan: React.FC<ExecutionPlanProps> = ({
  session,
  isBusy,
  onInterrupt,
  onRefresh,
}) => {
  const { plan, controls, status, ttl_remaining_seconds } = session;

  return (
    <section className="panel" aria-label="Execution Plan and Controls">
      <div className="panel-header">
        <h2 className="panel-title">
          <GitBranch size={18} color="#22d3ee" />
          2. Execution Plan & Intervention Controls
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span className="badge badge-cyan">{status.replace(/_/g, ' ')}</span>
          <span className="badge badge-slate">TTL {formatTtl(ttl_remaining_seconds)}</span>
        </div>
      </div>

      <p style={{ margin: '0 0 12px', fontSize: '0.88rem', color: '#cbd5e1' }}>
        <strong>Goal:</strong> {plan.goal_summary}
      </p>

      {plan.boundary_triggered && plan.boundary_note && (
        <div className="alert-banner alert-danger" style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: 2 }} />
            <div>
              <strong>Sandbox Boundary Enforced:</strong> {plan.boundary_note}
            </div>
          </div>
        </div>
      )}

      <div className="controls-bar">
        <div className="controls-buttons">
          <button
            type="button"
            className="btn btn-warning btn-sm"
            disabled={!controls.can_pause || isBusy}
            onClick={() => onInterrupt('pause')}
          >
            <Pause size={14} />
            Pause
          </button>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={!controls.can_resume || isBusy}
            onClick={() => onInterrupt('resume')}
          >
            <Play size={14} />
            Resume
          </button>
          <button
            type="button"
            className="btn btn-reject btn-sm"
            disabled={!controls.can_cancel || isBusy}
            onClick={() => onInterrupt('cancel')}
          >
            <XCircle size={14} />
            Cancel Task
          </button>
        </div>

        <button
          type="button"
          className="btn btn-sm"
          disabled={isBusy}
          onClick={onRefresh}
        >
          <RefreshCw size={14} />
          Refresh State
        </button>
      </div>

      <div className="steps-list">
        {plan.steps.map((step: PlanStep) => {
          const cardClass =
            step.status === 'running'
              ? 'is-running'
              : step.status === 'waiting_for_human'
                ? 'is-waiting'
                : step.status === 'rejected'
                  ? 'is-rejected'
                  : '';

          return (
            <article key={step.step_id} className={`step-card ${cardClass}`}>
              <div className="step-header">
                <div className="step-title-group">
                  {renderStepIcon(step.status)}
                  <span>
                    Step {step.order}: {step.title}
                  </span>
                </div>

                <div className="step-badges">
                  <span className={`badge risk-${step.risk}`}>{step.risk} risk</span>
                  {step.requires_approval && (
                    <span className="badge risk-medium">Human Gate</span>
                  )}
                  <span className="badge badge-slate">
                    {step.status.replace(/_/g, ' ')}
                  </span>
                </div>
              </div>

              <p className="step-desc">{step.description}</p>

              <div className="step-meta">
                <span>action: {step.action_id}</span>
                <span>policy: {step.policy_rule_id}</span>
                <span>target: {step.sandbox_target}</span>
                {step.depends_on.length > 0 && (
                  <span>depends on: {step.depends_on.join(', ')}</span>
                )}
              </div>

              <div className="step-reasoning">
                <strong>Operational Rationale:</strong> {step.reasoning_summary}
              </div>

              {step.output_summary && (
                <div
                  className={`step-output ${
                    step.status === 'rejected' || step.status === 'cancelled'
                      ? 'is-blocked'
                      : ''
                  }`}
                >
                  {step.output_summary}
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
};
