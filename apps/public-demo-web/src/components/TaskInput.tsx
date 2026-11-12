import React, { useState } from 'react';
import { BookOpen, ChevronDown, ChevronUp, Play, Sparkles } from 'lucide-react';
import type { SandboxDocument, ScenarioSummary } from '../api';

interface TaskInputProps {
  scenarios: ScenarioSummary[];
  sandboxDocuments: SandboxDocument[];
  isSubmitting: boolean;
  onSubmitTask: (task: string, scenarioId: string | null) => Promise<void>;
}

const MAX_TASK_CHARS = 300;

export const TaskInput: React.FC<TaskInputProps> = ({
  scenarios,
  sandboxDocuments,
  isSubmitting,
  onSubmitTask,
}) => {
  const defaultTask =
    scenarios[0]?.task ||
    'Prepare a comparison report from three sample research documents.';
  const [task, setTask] = useState<string>(defaultTask);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(
    scenarios[0]?.id ?? 'research_comparison'
  );
  const [showDocs, setShowDocs] = useState<boolean>(false);

  const trimmedLen = task.trim().length;
  const isValid = trimmedLen >= 3 && task.length <= MAX_TASK_CHARS;

  const handleSelectScenario = (scenario: ScenarioSummary) => {
    setTask(scenario.task);
    setSelectedScenarioId(scenario.id);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid || isSubmitting) return;
    await onSubmitTask(task.trim(), selectedScenarioId);
  };

  return (
    <section className="panel" aria-label="Task Input">
      <div className="panel-header">
        <h2 className="panel-title">
          <Sparkles size={18} color="#22d3ee" />
          1. Enter Task or Choose a Research Scenario
        </h2>
        <button
          type="button"
          className="btn btn-sm"
          onClick={() => setShowDocs((prev) => !prev)}
        >
          <BookOpen size={14} />
          Inspect Sandbox Docs ({sandboxDocuments.length})
          {showDocs ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>

      <form className="task-form" onSubmit={handleSubmit}>
        <textarea
          className="task-textarea"
          value={task}
          maxLength={MAX_TASK_CHARS}
          onChange={(e) => {
            setTask(e.target.value);
            setSelectedScenarioId(null);
          }}
          placeholder="Describe a task for R.I.O. to plan and execute inside the 3-document sandbox..."
          aria-label="Task prompt"
        />
        <div className="task-form-footer">
          <span
            className={`char-counter ${
              task.length >= MAX_TASK_CHARS - 30 ? 'near-limit' : ''
            }`}
          >
            {task.length} / {MAX_TASK_CHARS} characters (max 300 enforced server-side)
          </span>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={!isValid || isSubmitting}
          >
            <Play size={15} />
            {isSubmitting ? 'Generating Plan...' : 'Create Plan & Start Sandbox Run'}
          </button>
        </div>
      </form>

      {scenarios.length > 0 && (
        <div className="scenarios-grid" aria-label="Preset Demo Scenarios">
          {scenarios.map((scenario) => {
            const isSelected = selectedScenarioId === scenario.id;
            return (
              <button
                key={scenario.id}
                type="button"
                className={`scenario-card ${isSelected ? 'selected' : ''}`}
                onClick={() => handleSelectScenario(scenario)}
              >
                <div className="scenario-card-top">
                  <span className="scenario-title">{scenario.title}</span>
                  <span className={`badge risk-${scenario.expected_risk_peak}`}>
                    {scenario.expected_risk_peak} peak
                  </span>
                </div>
                <p className="scenario-desc">{scenario.description}</p>
              </button>
            );
          })}
        </div>
      )}

      {showDocs && sandboxDocuments.length > 0 && (
        <div className="docs-drawer">
          <div style={{ fontSize: '0.82rem', color: '#cbd5e1', fontWeight: 600 }}>
            Closed Sandbox Corpus (Only data R.I.O. can read — zero host filesystem access)
          </div>
          <div className="docs-grid">
            {sandboxDocuments.map((doc) => (
              <div key={doc.doc_id} className="doc-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <span className="badge badge-cyan">{doc.doc_id}</span>
                  <span className="mono" style={{ color: '#64748b' }}>
                    {doc.date}
                  </span>
                </div>
                <h4>{doc.title}</h4>
                <p style={{ margin: '0 0 6px', color: '#94a3b8' }}>{doc.summary}</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {Object.entries(doc.key_metrics).map(([k, v]) => (
                    <span key={k} className="badge badge-slate">
                      {k}: {v}
                    </span>
                  ))}
                </div>
                <div className="doc-caveat">Caveat: {doc.caveats}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
};
