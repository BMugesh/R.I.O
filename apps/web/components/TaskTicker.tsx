'use client';

import React from 'react';
import { Loader2, CheckCircle2, AlertCircle } from 'lucide-react';

interface TaskTickerProps {
  status?: string;
  isExecuting: boolean;
  error?: string;
}

export const TaskTicker: React.FC<TaskTickerProps> = ({ status, isExecuting, error }) => {
  if (!status && !isExecuting && !error) return null;

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900/80 border border-slate-800 backdrop-blur text-xs font-medium text-slate-300 animate-in fade-in slide-in-from-bottom-2 duration-200">
      {isExecuting && <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-400" />}
      {!isExecuting && !error && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
      {error && <AlertCircle className="w-3.5 h-3.5 text-rose-400" />}
      <span className="truncate">{error || status || 'Ready'}</span>
    </div>
  );
};
