import React, { useState } from 'react';
import { Check, ShieldAlert, ShieldCheck, X } from 'lucide-react';
import type { DecisionChoice, DemoSessionResponse } from '../api';

interface ApprovalPanelProps {
  session: DemoSessionResponse;
  isBusy: boolean;
  onDecision: (actionId: string, decision: DecisionChoice, reason?: string) => Promise<void>;
}

export const ApprovalPanel: React.FC<ApprovalPanelProps> = ({
  session,
  isBusy,
  onDecision,
}) => {
  const [reason, setReason] = useState<string>('');
  const pending = session.pending_approval;
  const isPaused = session.status === 'paused';

  if (!pending) {
    return (
      <section className="panel" aria-label="Approval Gate Status">
        <div className="panel-header">
          <h2 className="panel-title">
            <ShieldCheck size={18} color="#34d399" />
            3. Human Approval Gate
          </h2>
          <span className="badge badge-slate">
            {session.status === 'completed'
              ? 'Approved & Completed'
              : session.status === 'rejected'
                ? 'Halted by Rejection'
                : session.status === 'cancelled'
                  ? 'Cancelled'
                  : 'Waiting on Earlier Steps'}
          </span>
        </div>
        <p style={{ margin: 0, fontSize: '0.86rem', color: '#94a3b8' }}>
          {session.status === 'running'
            ? 'R.I.O. is executing low/medium-risk sandbox steps and will pause automatically when it reaches a high-risk human gate.'
            : session.status === 'completed'
              ? 'The high-risk gate was approved by the visitor, allowing the final simulated sandbox recording step to finish.'
              : session.status === 'rejected'
                ? 'The visitor rejected the gated action. R.I.O. halted execution and skipped all dependent downstream steps.'
                : session.status === 'cancelled'
                  ? 'Execution was cancelled before completion.'
                  : 'No human approval is currently awaiting a decision.'}
        </p>
      </section>
    );
  }

  const submitChoice = async (choice: DecisionChoice) => {
    if (!session.controls.can_decide || isBusy) return;
    await onDecision(pending.action_id, choice, reason);
    setReason('');
  };

  return (
    <section className="panel approval-active" aria-label="Pending Human Approval">
      <div className="panel-header">
        <h2 className="panel-title" style={{ color: '#fde68a' }}>
          <ShieldAlert size={19} color="#fbbf24" />
          3. Human Approval Required
        </h2>
        <span className={`badge risk-${pending.risk}`}>{pending.risk} risk</span>
      </div>

      <p style={{ margin: '0 0 8px', fontSize: '0.9rem', color: '#f8fafc' }}>
        <strong>{pending.title}</strong> — {pending.description}
      </p>

      <div className="step-meta" style={{ marginBottom: 10 }}>
        <span>action_id: {pending.action_id}</span>
        <span>rule: {pending.policy_rule_id}</span>
        <span>target: {pending.sandbox_target}</span>
      </div>

      <div className="consequence-grid">
        <div className="consequence-box" style={{ borderColor: 'rgba(52, 211, 153, 0.35)' }}>
          <strong style={{ color: '#34d399' }}>If You Approve</strong>
          <span style={{ color: '#cbd5e1' }}>{pending.if_approved}</span>
        </div>
        <div className="consequence-box" style={{ borderColor: 'rgba(251, 113, 133, 0.35)' }}>
          <strong style={{ color: '#fb7185' }}>If You Reject</strong>
          <span style={{ color: '#cbd5e1' }}>{pending.if_rejected}</span>
        </div>
      </div>

      {isPaused && (
        <div className="alert-banner alert-warning" style={{ marginBottom: 12 }}>
          Execution is currently paused. Click <strong>Resume</strong> in the controls bar before submitting a decision.
        </div>
      )}

      <input
        type="text"
        className="approval-reason-input"
        value={reason}
        maxLength={200}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Optional audit note (e.g., Citations look consistent / Hold for manual review)..."
        aria-label="Approval decision rationale"
      />

      <div className="approval-actions">
        <button
          type="button"
          className="btn btn-approve"
          disabled={!session.controls.can_decide || isBusy}
          onClick={() => submitChoice('approve')}
        >
          <Check size={16} />
          Approve & Continue
        </button>
        <button
          type="button"
          className="btn btn-reject"
          disabled={!session.controls.can_decide || isBusy}
          onClick={() => submitChoice('reject')}
        >
          <X size={16} />
          Reject & Halt
        </button>
      </div>
    </section>
  );
};
