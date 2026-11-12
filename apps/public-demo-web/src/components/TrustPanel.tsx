import React from 'react';
import {
  AlertOctagon,
  CheckCircle2,
  FileCheck2,
  Gauge,
  Info,
  Link2,
  Scale,
} from 'lucide-react';
import type { TrustSummary } from '../api';

interface TrustPanelProps {
  trust: TrustSummary;
  onSelectEventId?: (eventId: string) => void;
}

export const TrustPanel: React.FC<TrustPanelProps> = ({ trust, onSelectEventId }) => {
  const dims = trust.calibration_dimensions;
  const artifact = trust.simulated_artifact;

  const isRejectedArtifact = artifact?.artifact_state === 'export_rejected_draft_only';
  const isCancelledArtifact = artifact?.artifact_state === 'cancelled_draft_only';
  const isApprovedArtifact = artifact?.artifact_state === 'export_approved_simulated';

  return (
    <section className="panel" aria-label="Trust and Evidence Panel">
      <div className="panel-header">
        <h2 className="panel-title">
          <Scale size={18} color="#34d399" />
          5. Trust Calibration, Traceability & Evidence
        </h2>
        <span className="badge badge-cyan">
          {trust.planner_source === 'groq_assisted'
            ? `Groq (${trust.planner_model || 'LLM'}) + Policy`
            : 'Deterministic Fallback + Policy'}
        </span>
      </div>

      <div className="trust-section">
        <h3>
          <Gauge size={13} style={{ verticalAlign: 'middle', marginRight: 6 }} />
          Separated Calibration Dimensions (No Unvalidated % Scores)
        </h3>
        <div className="calibration-grid">
          <div className="calibration-card">
            <div className="calibration-card-top">
              <span className="calibration-axis">Policy Verification</span>
              <span
                className={`badge ${
                  dims.policy_verification_status === 'halted_by_human'
                    ? 'risk-high'
                    : 'risk-low'
                }`}
              >
                {dims.policy_verification_status.replace(/_/g, ' ')}
              </span>
            </div>
            <p className="calibration-note">{dims.policy_verification_note}</p>
          </div>

          <div className="calibration-card">
            <div className="calibration-card-top">
              <span className="calibration-axis">Evidence Grounding</span>
              <span className="badge badge-cyan">
                {dims.cited_document_ids.length} / {dims.total_sandbox_documents} docs
              </span>
            </div>
            <p className="calibration-note">{dims.evidence_completeness_label}</p>
          </div>

          <div className="calibration-card">
            <div className="calibration-card-top">
              <span className="calibration-axis">Model Output Certainty</span>
              <span className="badge risk-medium">
                {dims.model_certainty_label.replace(/_/g, ' ')}
              </span>
            </div>
            <p className="calibration-note">{dims.model_certainty_note}</p>
          </div>

          <div className="calibration-card">
            <div className="calibration-card-top">
              <span className="calibration-axis">Execution Certainty</span>
              <span
                className={`badge ${
                  dims.execution_certainty_label === 'export_rejected_no_write'
                    ? 'risk-high'
                    : 'badge-slate'
                }`}
              >
                {dims.execution_certainty_label.replace(/_/g, ' ')}
              </span>
            </div>
            <p className="calibration-note">{dims.execution_certainty_note}</p>
          </div>
        </div>

        <ul className="bullet-list" style={{ marginTop: 10 }}>
          {trust.uncertainty_notes.map((note, idx) => (
            <li key={idx}>{note}</li>
          ))}
        </ul>
      </div>

      <div className="trust-section">
        <h3>
          <Info size={13} style={{ verticalAlign: 'middle', marginRight: 6 }} />
          What R.I.O. Did & Why
        </h3>
        {trust.what_rio_did.length > 0 ? (
          <ul className="bullet-list" style={{ marginBottom: 10 }}>
            {trust.what_rio_did.map((item, idx) => (
              <li key={idx} style={{ color: '#e2e8f0' }}>
                {item}
              </li>
            ))}
          </ul>
        ) : (
          <p style={{ margin: '0 0 10px', fontSize: '0.82rem', color: '#64748b' }}>
            Waiting for initial step completion...
          </p>
        )}
        <ul className="bullet-list">
          {trust.why_decisions_made.map((reason, idx) => (
            <li key={idx}>{reason}</li>
          ))}
        </ul>
      </div>

      <div className="trust-section">
        <h3>
          <FileCheck2 size={13} style={{ verticalAlign: 'middle', marginRight: 6 }} />
          Traceable Evidence Ledger ({trust.evidence.length})
        </h3>
        {trust.evidence.length === 0 ? (
          <p style={{ margin: 0, fontSize: '0.82rem', color: '#64748b' }}>
            Traceable evidence links appear here as sandbox steps and gates execute.
          </p>
        ) : (
          trust.evidence.map((ev) => (
            <div key={ev.evidence_id} className="evidence-item">
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 8,
                  flexWrap: 'wrap',
                  marginBottom: 6,
                }}
              >
                <span className="mono" style={{ color: '#22d3ee' }}>
                  {ev.source}
                </span>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <span
                    className={`badge ${
                      ev.verification_status === 'verified_rule'
                        ? 'risk-low'
                        : ev.verification_status === 'rejected_by_human' ||
                            ev.verification_status === 'blocked_by_policy'
                          ? 'risk-high'
                          : 'badge-cyan'
                    }`}
                  >
                    {ev.certainty_label}
                  </span>
                </div>
              </div>

              <div className="evidence-trace-row">
                <button
                  type="button"
                  className="trace-link-btn"
                  onClick={() => onSelectEventId?.(ev.event_id)}
                  title="Highlight linked timeline event"
                >
                  <Link2 size={12} />
                  Event #{String(ev.event_seq).padStart(2, '0')} ({ev.event_id})
                </button>
                <span className="badge badge-slate">Rule: {ev.policy_rule_id}</span>
                <span className="badge badge-slate">
                  Docs: {ev.document_ids.length > 0 ? ev.document_ids.join(', ') : 'None'}
                </span>
              </div>

              <div style={{ color: '#cbd5e1', marginTop: 6 }}>{ev.excerpt}</div>
            </div>
          ))
        )}
      </div>

      {artifact && (
        <div className="trust-section">
          <h3>Draft vs. Export Lifecycle</h3>
          <div
            className={`artifact-box ${
              isRejectedArtifact || isCancelledArtifact ? 'is-rejected' : ''
            }`}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: 8,
                flexWrap: 'wrap',
              }}
            >
              <strong style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                {isRejectedArtifact || isCancelledArtifact ? (
                  <AlertOctagon size={16} color="#fb7185" />
                ) : (
                  <CheckCircle2 size={16} color={isApprovedArtifact ? '#34d399' : '#fbbf24'} />
                )}
                {artifact.title}
              </strong>
              <span
                className={`badge ${
                  isRejectedArtifact || isCancelledArtifact
                    ? 'risk-high'
                    : isApprovedArtifact
                      ? 'risk-low'
                      : 'risk-medium'
                }`}
              >
                {artifact.artifact_state.replace(/_/g, ' ')}
              </span>
            </div>

            <div className="artifact-triplet">
              <span className="badge badge-slate">
                Draft generated in session memory: {artifact.draft_created_in_memory ? 'Yes' : 'No'}
              </span>
              <span
                className={`badge ${
                  isRejectedArtifact || isCancelledArtifact
                    ? 'risk-high'
                    : artifact.export_approved
                      ? 'risk-low'
                      : 'risk-medium'
                }`}
              >
                Export action:{' '}
                {isRejectedArtifact
                  ? 'Rejected'
                  : isCancelledArtifact
                    ? 'Cancelled'
                    : artifact.export_approved
                      ? 'Approved (Simulated)'
                      : 'Pending Approval'}
              </span>
              <span className="badge badge-slate">
                External publication performed: {artifact.external_publication_performed ? 'Yes' : 'No'}
              </span>
            </div>

            <div
              style={{
                marginTop: 8,
                fontSize: '0.78rem',
                color: isRejectedArtifact || isCancelledArtifact ? '#fecdd3' : '#fde68a',
              }}
            >
              {artifact.notice}
            </div>
            <pre className="artifact-content">{artifact.content}</pre>
          </div>
        </div>
      )}
    </section>
  );
};
