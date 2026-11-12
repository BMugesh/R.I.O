import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Cpu,
  Eye,
  Lock,
  RotateCcw,
  Shield,
  SlidersHorizontal,
} from 'lucide-react';
import {
  ApiError,
  checkHealth,
  createSession,
  DecisionChoice,
  DemoSessionResponse,
  fetchScenarios,
  fetchSession,
  InterruptCommand,
  SandboxDocument,
  ScenarioSummary,
  submitDecision,
  submitInterrupt,
} from './api';
import { ApprovalPanel } from './components/ApprovalPanel';
import { EventTimeline } from './components/EventTimeline';
import { ExecutionPlan } from './components/ExecutionPlan';
import { TaskInput } from './components/TaskInput';
import { TrustPanel } from './components/TrustPanel';

const SESSION_STORAGE_KEY = 'rio_public_demo_session_id';

export const App: React.FC = () => {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [sandboxDocs, setSandboxDocs] = useState<SandboxDocument[]>([]);
  const [session, setSession] = useState<DemoSessionResponse | null>(null);
  const [backendStatus, setBackendStatus] = useState<
    'connecting' | 'waking' | 'ready' | 'error'
  >('connecting');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isActionBusy, setIsActionBusy] = useState<boolean>(false);
  const [highlightedEventId, setHighlightedEventId] = useState<string | null>(null);
  const mountedRef = useRef<boolean>(true);

  const loadInitialData = useCallback(async () => {
    setBackendStatus('connecting');
    setErrorMessage(null);

    const wakeTimer = window.setTimeout(() => {
      if (mountedRef.current) {
        setBackendStatus((curr) => (curr === 'connecting' ? 'waking' : curr));
      }
    }, 1800);

    try {
      await checkHealth();
      const scenData = await fetchScenarios();
      if (!mountedRef.current) return;
      setScenarios(scenData.scenarios);
      setSandboxDocs(scenData.sandbox_documents);
      setBackendStatus('ready');

      const savedId = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
      if (savedId) {
        try {
          const restored = await fetchSession(savedId);
          if (mountedRef.current) {
            setSession(restored);
          }
        } catch (err) {
          window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
          if (err instanceof ApiError && (err.status === 404 || err.status === 410)) {
            if (mountedRef.current) {
              setErrorMessage(
                'Your previous demo session expired or was cleared after a backend restart. Start a new run below.'
              );
            }
          }
        }
      }
    } catch (err) {
      if (!mountedRef.current) return;
      setBackendStatus('error');
      setErrorMessage(
        err instanceof Error
          ? `Could not reach the isolated R.I.O. demo API: ${err.message}`
          : 'Could not reach the isolated R.I.O. demo API.'
      );
    } finally {
      window.clearTimeout(wakeTimer);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void loadInitialData();
    return () => {
      mountedRef.current = false;
    };
  }, [loadInitialData]);

  // Poll backend only while execution is actively running
  useEffect(() => {
    if (!session || session.status !== 'running') return;
    const interval = window.setInterval(async () => {
      try {
        const updated = await fetchSession(session.session_id);
        if (mountedRef.current) {
          setSession(updated);
        }
      } catch (err) {
        if (!mountedRef.current) return;
        if (err instanceof ApiError && (err.status === 404 || err.status === 410)) {
          window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
          setSession(null);
          setErrorMessage(
            'Session expired or purged after backend restart (ephemeral 30-minute memory only). Please start a new session.'
          );
        }
      }
    }, 650);
    return () => window.clearInterval(interval);
  }, [session?.session_id, session?.status]);

  // Smooth client-side TTL ticker between API refreshes
  useEffect(() => {
    if (!session) return;
    const activeStates = ['planned', 'running', 'waiting_for_human', 'paused'];
    if (!activeStates.includes(session.status)) return;
    const timer = window.setInterval(() => {
      setSession((prev) =>
        prev && prev.ttl_remaining_seconds > 0
          ? { ...prev, ttl_remaining_seconds: prev.ttl_remaining_seconds - 1 }
          : prev
      );
    }, 1000);
    return () => window.clearInterval(timer);
  }, [session?.session_id, session?.status]);

  const handleApiError = (err: unknown) => {
    if (err instanceof ApiError) {
      if (err.status === 404 || err.status === 410) {
        window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
        setSession(null);
      }
      setErrorMessage(err.message);
    } else if (err instanceof Error) {
      setErrorMessage(err.message);
    } else {
      setErrorMessage('Unexpected error communicating with the demo API.');
    }
  };

  const handleCreateSession = async (task: string, scenarioId: string | null) => {
    setIsSubmitting(true);
    setErrorMessage(null);
    setHighlightedEventId(null);
    try {
      const created = await createSession(task, scenarioId);
      window.sessionStorage.setItem(SESSION_STORAGE_KEY, created.session_id);
      setSession(created);
    } catch (err) {
      handleApiError(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDecision = async (
    actionId: string,
    decision: DecisionChoice,
    reason?: string
  ) => {
    if (!session) return;
    setIsActionBusy(true);
    setErrorMessage(null);
    try {
      const updated = await submitDecision(session.session_id, actionId, decision, reason);
      setSession(updated);
    } catch (err) {
      handleApiError(err);
    } finally {
      setIsActionBusy(false);
    }
  };

  const handleInterrupt = async (command: InterruptCommand) => {
    if (!session) return;
    setIsActionBusy(true);
    setErrorMessage(null);
    try {
      const updated = await submitInterrupt(session.session_id, command);
      setSession(updated);
    } catch (err) {
      handleApiError(err);
    } finally {
      setIsActionBusy(false);
    }
  };

  const handleRefresh = async () => {
    if (!session) return;
    setIsActionBusy(true);
    setErrorMessage(null);
    try {
      const updated = await fetchSession(session.session_id);
      setSession(updated);
    } catch (err) {
      handleApiError(err);
    } finally {
      setIsActionBusy(false);
    }
  };

  const handleClearSession = () => {
    window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
    setSession(null);
    setHighlightedEventId(null);
    setErrorMessage(null);
  };

  return (
    <div className="app-shell">
      <div className="top-banner" role="note">
        <div className="top-banner-left">
          <Lock size={15} color="#22d3ee" />
          <span>
            <strong>Isolated Public Research Sandbox:</strong> Simulated actions against 3 synthetic
            documents only. Personal local agents, filesystem, devices, and MCP remain offline.
          </span>
        </div>
        <div className="top-banner-right">
          <span
            className={`badge ${
              backendStatus === 'ready'
                ? 'risk-low'
                : backendStatus === 'error'
                  ? 'risk-high'
                  : 'risk-medium'
            }`}
          >
            API: {backendStatus}
          </span>
          {session && (
            <button type="button" className="btn btn-sm" onClick={handleClearSession}>
              <RotateCcw size={13} />
              New Session
            </button>
          )}
        </div>
      </div>

      <header className="header-bar">
        <div className="brand-block">
          <h1>
            <Cpu size={26} color="#22d3ee" />
            R.I.O. Public Sandbox
            <span className="brand-tag">Research Demo v0.2</span>
          </h1>
          <p className="brand-subtitle">
            Inspect how R.I.O. (Reasoning Intelligence Orchestration) plans tasks, evaluates
            deterministic risk policies, gates high-impact actions on human approval, and calibrates
            evidence transparency.
          </p>
        </div>

        <div className="research-pillars" aria-label="Research Principles">
          <span className="pillar-pill">
            <Eye size={14} color="#22d3ee" />
            Transparency
          </span>
          <span className="pillar-pill">
            <SlidersHorizontal size={14} color="#fbbf24" />
            Human Control
          </span>
          <span className="pillar-pill">
            <Shield size={14} color="#34d399" />
            Calibrated Trust
          </span>
        </div>
      </header>

      {backendStatus === 'waking' && (
        <div className="alert-banner alert-warning">
          <div>
            <strong>Waking up isolated backend service...</strong> Free-tier web services sleep
            after 15 minutes of inactivity and typically wake within ~45–60 seconds.
          </div>
        </div>
      )}

      {backendStatus === 'error' && (
        <div className="alert-banner alert-danger">
          <div>{errorMessage}</div>
          <button type="button" className="btn btn-sm" onClick={() => void loadInitialData()}>
            Retry Connection
          </button>
        </div>
      )}

      {backendStatus !== 'error' && errorMessage && (
        <div className="alert-banner alert-danger">
          <div>{errorMessage}</div>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => setErrorMessage(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      <TaskInput
        scenarios={scenarios}
        sandboxDocuments={sandboxDocs}
        isSubmitting={isSubmitting}
        onSubmitTask={handleCreateSession}
      />

      {session ? (
        <div className="workspace-grid">
          <div className="column-stack">
            <ExecutionPlan
              session={session}
              isBusy={isActionBusy}
              onInterrupt={handleInterrupt}
              onRefresh={handleRefresh}
            />
            <EventTimeline
              events={session.events}
              highlightedEventId={highlightedEventId}
            />
          </div>

          <div className="column-stack">
            <ApprovalPanel
              session={session}
              isBusy={isActionBusy}
              onDecision={handleDecision}
            />
            <TrustPanel
              trust={session.trust_summary}
              onSelectEventId={(eventId) => setHighlightedEventId(eventId)}
            />
          </div>
        </div>
      ) : (
        <div className="panel" style={{ marginTop: 20, textAlign: 'center', padding: '32px 20px' }}>
          <p style={{ margin: '0 0 6px', fontSize: '1rem', fontWeight: 600 }}>
            Ready to simulate an orchestrated workflow
          </p>
          <p style={{ margin: 0, fontSize: '0.88rem', color: '#94a3b8' }}>
            Submit the default document-comparison task above or enter a custom prompt to inspect
            R.I.O.&apos;s step plan, policy risk classification, approval gate, and trust panel.
          </p>
        </div>
      )}
    </div>
  );
};

export default App;
