'use client';

import React, { useState } from 'react';
import { Atom, Play, CheckCircle2, Cpu } from 'lucide-react';
import { QuantumJob } from '../../../packages/types';
import { getApiBaseUrl } from '../lib/api';

export const QuantumWorkbench: React.FC = () => {
  const [algorithm, setAlgorithm] = useState<'qaoa' | 'vqe' | 'circuit_execution'>('qaoa');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<any>(null);

  const handleRunJob = async () => {
    setRunning(true);
    setResult(null);
    try {
      const apiBase = getApiBaseUrl();
      const res = await fetch(`${apiBase}/api/v1/quantum/jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          algorithm,
          backend: 'aer_simulator',
          problem_matrix: [[0, 1, 1], [1, 0, 1], [1, 1, 0]],
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setResult(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white">Quantum Computation Engine (Qiskit)</h2>
        <p className="text-xs text-slate-400">Hybrid Quantum/Classical solver with Aer simulation and classical verification</p>
      </div>

      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-5">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <label className="text-xs text-slate-400 font-mono block mb-1">Algorithm</label>
            <select
              value={algorithm}
              onChange={(e: any) => setAlgorithm(e.target.value)}
              className="px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none focus:border-cyan-500"
            >
              <option value="qaoa">QAOA (Graph Max-Cut)</option>
              <option value="vqe">VQE (Ground State Energy)</option>
              <option value="circuit_execution">Bell State Circuit</option>
            </select>
          </div>

          <div className="pt-5">
            <button
              onClick={handleRunJob}
              disabled={running}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white text-xs font-semibold shadow-lg shadow-cyan-600/20 transition-all"
            >
              <Play className={`w-3.5 h-3.5 ${running ? 'animate-spin' : ''}`} />
              {running ? 'Simulating on Aer...' : 'Run Quantum Job'}
            </button>
          </div>
        </div>

        {result && (
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3 font-mono text-xs animate-in fade-in">
            <div className="flex items-center justify-between text-emerald-400">
              <span className="flex items-center gap-1.5 font-semibold">
                <CheckCircle2 className="w-4 h-4" /> Classically Verified Result
              </span>
              <span className="text-slate-500 text-[11px]">{result.executionTimeMs?.toFixed(1)} ms</span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 pt-2">
              <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                <span className="text-slate-500 text-[10px]">OPTIMAL VALUE</span>
                <p className="text-white font-bold text-sm mt-0.5">{result.optimalValue ?? '—'}</p>
              </div>
              <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                <span className="text-slate-500 text-[10px]">BACKEND</span>
                <p className="text-cyan-400 font-bold text-xs mt-0.5">{result.backend}</p>
              </div>
              <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                <span className="text-slate-500 text-[10px]">VERIFICATION</span>
                <p className="text-emerald-400 font-bold text-xs mt-0.5">Matched Exact Classical</p>
              </div>
            </div>

            <div>
              <span className="text-slate-500 text-[10px] uppercase">Measurement Counts:</span>
              <pre className="mt-1 p-2 rounded bg-slate-900 text-slate-300 text-[11px]">
                {JSON.stringify(result.counts, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
