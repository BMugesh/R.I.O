'use client';

import React, { useEffect, useState } from 'react';
import { Blocks, Wrench, Shield, CheckCircle2 } from 'lucide-react';
import { MCPManifest, ToolDefinition } from '../../../packages/types';
import { getApiBaseUrl } from '../lib/api';

export const MCPExplorer: React.FC = () => {
  const [servers, setServers] = useState<MCPManifest[]>([]);
  const [tools, setTools] = useState<ToolDefinition[]>([]);

  useEffect(() => {
    const apiBase = getApiBaseUrl();
    fetch(`${apiBase}/api/v1/mcp`).then(r => r.json()).then(setServers).catch(console.error);
    fetch(`${apiBase}/api/v1/tools`).then(r => r.json()).then(setTools).catch(console.error);
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white">Model Context Protocol (MCP) & Tools</h2>
        <p className="text-xs text-slate-400">Connected external protocol servers, capability schemas, and tools</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* MCP Servers */}
        <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
          <div className="flex items-center gap-2.5 text-cyan-400">
            <Blocks className="w-5 h-5" />
            <h3 className="text-sm font-semibold text-white">Registered MCP Servers</h3>
          </div>

          <div className="space-y-2.5">
            {servers.map((s) => (
              <div key={s.id} className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-semibold text-white">{s.name}</h4>
                  <span className="text-[10px] font-mono text-slate-500">{s.id} ({s.transport})</span>
                </div>
                <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-mono text-[10px] flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> Active
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Tools Catalog */}
        <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
          <div className="flex items-center gap-2.5 text-purple-400">
            <Wrench className="w-5 h-5" />
            <h3 className="text-sm font-semibold text-white">Tool Registry ({tools.length})</h3>
          </div>

          <div className="space-y-2.5 max-h-96 overflow-y-auto pr-1">
            {tools.map((t) => (
              <div key={t.id} className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-cyan-300 font-mono">{t.name}</span>
                  <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-slate-900 text-slate-400">
                    {t.riskLevel}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400">{t.description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
