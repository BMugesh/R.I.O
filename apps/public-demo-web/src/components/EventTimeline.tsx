import React, { useEffect, useRef, useState } from 'react';
import { Activity, Code2 } from 'lucide-react';
import type { ExecutionEvent } from '../api';

interface EventTimelineProps {
  events: ExecutionEvent[];
  highlightedEventId?: string | null;
}

type EventFilter = 'all' | 'policy' | 'steps';

function formatPreciseTimestamp(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  const ms = String(d.getMilliseconds()).padStart(3, '0');
  return `${hh}:${mm}:${ss}.${ms}`;
}

export const EventTimeline: React.FC<EventTimelineProps> = ({
  events,
  highlightedEventId,
}) => {
  const [filter, setFilter] = useState<EventFilter>('all');
  const [showRaw, setShowRaw] = useState<boolean>(false);
  const rowRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    if (highlightedEventId && rowRefs.current[highlightedEventId]) {
      setFilter('all');
      rowRefs.current[highlightedEventId]?.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
      });
    }
  }, [highlightedEventId]);

  const orderedEvents = [...events].sort((a, b) => a.seq - b.seq);

  const filtered = orderedEvents.filter((evt) => {
    if (filter === 'policy') {
      return (
        evt.event_type.includes('approval') ||
        evt.event_type.includes('policy') ||
        evt.event_type.includes('paused') ||
        evt.event_type.includes('resumed') ||
        evt.event_type.includes('cancelled')
      );
    }
    if (filter === 'steps') {
      return evt.event_type.startsWith('step_') || evt.event_type.startsWith('execution_');
    }
    return true;
  });

  return (
    <section className="panel" aria-label="Execution Event Timeline">
      <div className="panel-header">
        <h2 className="panel-title">
          <Activity size={18} color="#22d3ee" />
          4. Live Event Timeline ({orderedEvents.length})
        </h2>

        <div className="filter-tabs">
          <button
            type="button"
            className={`btn btn-sm ${filter === 'all' ? 'btn-primary' : ''}`}
            onClick={() => setFilter('all')}
          >
            All
          </button>
          <button
            type="button"
            className={`btn btn-sm ${filter === 'policy' ? 'btn-primary' : ''}`}
            onClick={() => setFilter('policy')}
          >
            Policy & Gates
          </button>
          <button
            type="button"
            className={`btn btn-sm ${filter === 'steps' ? 'btn-primary' : ''}`}
            onClick={() => setFilter('steps')}
          >
            Steps
          </button>
          <button
            type="button"
            className={`btn btn-sm ${showRaw ? 'btn-primary' : ''}`}
            onClick={() => setShowRaw((p) => !p)}
          >
            <Code2 size={13} />
            JSON
          </button>
        </div>
      </div>

      <div className="timeline-list">
        {filtered.map((evt) => {
          const isHighlighted = highlightedEventId === evt.event_id;
          return (
            <div
              key={evt.event_id}
              ref={(el) => {
                rowRefs.current[evt.event_id] = el;
              }}
              className={`event-row ${isHighlighted ? 'is-highlighted' : ''}`}
            >
              <div className="event-top">
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <span className="seq-pill">#{String(evt.seq).padStart(2, '0')}</span>
                  <span className="badge badge-cyan">{evt.event_type}</span>
                  {evt.action_id && <span className="badge badge-slate">{evt.action_id}</span>}
                  {evt.risk && <span className={`badge risk-${evt.risk}`}>{evt.risk}</span>}
                  {evt.policy_rule_id && (
                    <span className="badge badge-slate">{evt.policy_rule_id}</span>
                  )}
                </div>
                <span className="mono" style={{ fontSize: '0.71rem', color: '#94a3b8' }}>
                  {formatPreciseTimestamp(evt.timestamp)} · {evt.event_id}
                </span>
              </div>
              <p className="event-summary">{evt.summary}</p>
              {showRaw && <pre className="raw-json">{JSON.stringify(evt, null, 2)}</pre>}
            </div>
          );
        })}
      </div>
    </section>
  );
};
