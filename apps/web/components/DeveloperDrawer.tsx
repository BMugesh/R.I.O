'use client';

import React, { useState } from 'react';
import { Terminal, Cpu, CheckCircle, Clock, X, ArrowRight, ShieldCheck, Layers } from 'lucide-react';
import { DeveloperTrace } from '../../../packages/types';

interface DeveloperDrawerProps {
  trace: DeveloperTrace | null;
  isOpen: boolean;
  onClose: () => void;
}

export const DeveloperDrawer: React.FC<DeveloperDrawerProps> = ({ trace, isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'dag' | 'steps' | 'raw'>('dag');

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-40 w-full max-w-2xl bg-slate-900/95 border-l border-slate-800 shadow-2xl backdrop-blur-xl flex flex-col animate-in slide-in-from-right duration-300">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/40">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
            <Terminal className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white">Developer Execution Inspector</h2>
            <p className="text-xs text-slate-400">R.I.O. Internal Reasoning & DAG Architecture</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Meta Bar */}
      <div className="grid grid-cols-3 gap-2 p-4 bg-slate-950/60 border-b border-slate-800 text-xs">
        <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800">
          <span className="text-slate-500 font-mono">MODEL ROUTED</span>
          <p className="font-mono text-cyan-400 truncate font-semibold mt-0.5">{trace?.modelId || 'llama-3.3-70b-versatile'}</p>
        </div>
        <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800">
          <span className="text-slate-500 font-mono">PRIMARY AGENT</span>
          <p className="font-mono text-purple-400 truncate font-semibold mt-0.5">{trace?.agentId || 'conversation_agent'}</p>
        </div>
        <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800">
          <span className="text-slate-500 font-mono">LATENCY</span>
          <p className="font-mono text-emerald-400 font-semibold mt-0.5">{trace?.latencyMs ? `${trace.latencyMs.toFixed(0)} ms` : '—'}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-800 px-6 bg-slate-950/20 text-xs font-medium">
        <button
          onClick={() => setActiveTab('dag')}
          className={`py-3 px-4 border-b-2 transition-colors ${activeTab === 'dag' ? 'border-cyan-500 text-cyan-400' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
        >
          Task Graph (DAG)
        </button>
        <button
          onClick={() => setActiveTab('steps')}
          className={`py-3 px-4 border-b-2 transition-colors ${activeTab === 'steps' ? 'border-cyan-500 text-cyan-400' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
        >
          Verification & Evidence
        </button>
        <button
          onClick={() => setActiveTab('raw')}
          className={`py-3 px-4 border-b-2 transition-colors ${activeTab === 'raw' ? 'border-cyan-500 text-cyan-400' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
        >
          Raw JSON Trace
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4 font-mono text-xs">
        {activeTab === 'dag' && (
          <div className="space-y-3">
            <h4 className="text-slate-400 uppercase tracking-wider font-semibold text-[11px] mb-2 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-cyan-400" />
              Execution Steps ({trace?.steps?.length || 0})
            </h4>
            {trace?.steps && trace.steps.length > 0 ? (
              trace.steps.map((step, idx) => (
                <div key={step.id || idx} className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 relative space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 font-semibold">
                      Step {idx + 1}: {step.name}
                    </span>
                    <span className="text-[10px] uppercase px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-semibold">
                      {step.status}
                    </span>
                  </div>
                  <p className="text-slate-400 font-sans text-xs">{step.description}</p>
                  <div className="grid grid-cols-2 gap-2 text-[11px] pt-1 text-slate-400">
                    <div>Agent: <span className="text-purple-400">{step.agentId}</span></div>
                    <div>Action: <span className="text-amber-400">{step.action.actionType}</span></div>
                  </div>
                </div>
              ))
            ) : (
              <div className="p-8 text-center text-slate-500 font-sans">
                Direct conversational path (No multi-step DAG needed).
              </div>
            )}
          </div>
        )}

        {activeTab === 'steps' && (
          <div className="space-y-4">
            <h4 className="text-slate-400 uppercase tracking-wider font-semibold text-[11px] flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              Verified Evidence Records
            </h4>
            {trace?.steps && trace.steps.some(s => s.evidence && s.evidence.length > 0) ? (
              trace.steps.map((step, sIdx) =>
                step.evidence?.map((ev, eIdx) => (
                  <div key={`${sIdx}-${eIdx}`} className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5">
                    <div className="flex items-center justify-between text-emerald-400">
                      <span>{ev.type} ({ev.source})</span>
                      <span className="text-xs">Confidence: {(ev.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <pre className="text-[10px] text-slate-400 bg-slate-900/80 p-2.5 rounded-lg overflow-x-auto">
                      {JSON.stringify(ev.data, null, 2)}
                    </pre>
                  </div>
                ))
              )
            ) : (
              <div className="p-8 text-center text-slate-500 font-sans">
                No active step evidence required for this message.
              </div>
            )}
          </div>
        )}

        {activeTab === 'raw' && (
          <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-[11px] text-slate-300 overflow-x-auto leading-relaxed">
            {JSON.stringify(trace, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
};
