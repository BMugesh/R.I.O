'use client';

import React from 'react';
import { ShieldAlert, Check, X } from 'lucide-react';
import { ApprovalRequest } from '../../../packages/types';

interface ApprovalModalProps {
  request: ApprovalRequest | null;
  onDecision: (requestId: string, approved: boolean) => void;
}

export const ApprovalModal: React.FC<ApprovalModalProps> = ({ request, onDecision }) => {
  if (!request) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-md rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl p-6 text-slate-100">
        <div className="flex items-center gap-3 text-amber-400 mb-4">
          <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-white">Action Requires Approval</h3>
            <p className="text-xs text-slate-400">Risk Level: <span className="uppercase font-mono text-amber-400">{request.riskLevel}</span></p>
          </div>
        </div>

        <div className="space-y-3 mb-6 bg-slate-950/60 p-4 rounded-xl border border-slate-800 text-sm">
          <div>
            <span className="text-xs text-slate-500 uppercase tracking-wider font-mono">Action</span>
            <p className="font-medium text-slate-200">{request.actionType}</p>
          </div>
          <div>
            <span className="text-xs text-slate-500 uppercase tracking-wider font-mono">Details</span>
            <p className="text-slate-300 text-xs mt-0.5">{request.description}</p>
          </div>
          {request.target && (
            <div>
              <span className="text-xs text-slate-500 uppercase tracking-wider font-mono">Target</span>
              <p className="font-mono text-xs text-cyan-400">{request.target}</p>
            </div>
          )}
        </div>

        <div className="flex gap-3">
          <button
            onClick={() => onDecision(request.id, false)}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium transition-colors"
          >
            <X className="w-4 h-4" />
            Deny
          </button>
          <button
            onClick={() => onDecision(request.id, true)}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-medium shadow-lg shadow-cyan-600/20 transition-all"
          >
            <Check className="w-4 h-4" />
            Approve
          </button>
        </div>
      </div>
    </div>
  );
};
