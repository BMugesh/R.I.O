'use client';

import React, { useState } from 'react';
import { MessageSquare, Laptop, Brain, Blocks, Atom } from 'lucide-react';
import { ChatView } from '../components/ChatView';
import { DeviceManager } from '../components/DeviceManager';
import { MemoryViewer } from '../components/MemoryViewer';
import { MCPExplorer } from '../components/MCPExplorer';
import { QuantumWorkbench } from '../components/QuantumWorkbench';

export default function Home() {
  const [activeTab, setActiveTab] = useState<'chat' | 'devices' | 'memory' | 'mcp' | 'quantum'>('chat');
  const [developerMode, setDeveloperMode] = useState(false);

  return (
    <main className="flex flex-col md:flex-row h-screen w-screen overflow-hidden bg-slate-950 text-slate-100">
      {/* Desktop Left Sidebar (hidden on mobile) */}
      <aside className="hidden md:flex md:w-60 shrink-0 border-r border-slate-800/80 bg-slate-950 flex-col justify-between p-3">
        <div className="space-y-6">
          {/* Brand */}
          <div className="flex items-center gap-3 px-2 py-3">
            <div className="w-9 h-9 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 font-black text-base shadow-inner">
              R
            </div>
            <div>
              <span className="text-sm font-bold tracking-wider text-white">R.I.O.</span>
              <p className="text-[10px] text-slate-500 font-mono">PERSONAL AI OS</p>
            </div>
          </div>

          {/* Navigation Items */}
          <nav className="space-y-1">
            <button
              onClick={() => setActiveTab('chat')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition-all ${
                activeTab === 'chat'
                  ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <MessageSquare className="w-4 h-4 shrink-0" />
              <span>Assistant Chat</span>
            </button>

            <button
              onClick={() => setActiveTab('devices')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition-all ${
                activeTab === 'devices'
                  ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <Laptop className="w-4 h-4 shrink-0" />
              <span>Devices</span>
            </button>

            <button
              onClick={() => setActiveTab('memory')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition-all ${
                activeTab === 'memory'
                  ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <Brain className="w-4 h-4 shrink-0" />
              <span>Memory & Facts</span>
            </button>

            <button
              onClick={() => setActiveTab('mcp')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition-all ${
                activeTab === 'mcp'
                  ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <Blocks className="w-4 h-4 shrink-0" />
              <span>MCP & Tools</span>
            </button>

            <button
              onClick={() => setActiveTab('quantum')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition-all ${
                activeTab === 'quantum'
                  ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <Atom className="w-4 h-4 shrink-0" />
              <span>Quantum Engine</span>
            </button>
          </nav>
        </div>

        {/* Footer info */}
        <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-[11px] text-slate-500 font-mono">
          <div>Status: <span className="text-emerald-400">Core Active</span></div>
          <div>Provider: <span className="text-cyan-400">Groq Fast</span></div>
        </div>
      </aside>

      {/* Main Content Area */}
      <section className="flex-1 flex flex-col h-full w-full overflow-hidden bg-slate-900/20">
        {activeTab === 'chat' && (
          <ChatView
            developerMode={developerMode}
            onToggleDeveloperMode={() => setDeveloperMode(!developerMode)}
          />
        )}
        {activeTab === 'devices' && (
          <div className="flex-1 overflow-y-auto p-4 sm:p-8">
            <DeviceManager />
          </div>
        )}
        {activeTab === 'memory' && (
          <div className="flex-1 overflow-y-auto p-4 sm:p-8">
            <MemoryViewer />
          </div>
        )}
        {activeTab === 'mcp' && (
          <div className="flex-1 overflow-y-auto p-4 sm:p-8">
            <MCPExplorer />
          </div>
        )}
        {activeTab === 'quantum' && (
          <div className="flex-1 overflow-y-auto p-4 sm:p-8">
            <QuantumWorkbench />
          </div>
        )}
      </section>

      {/* Mobile Bottom Navigation Bar (Visible only on mobile screens < md) */}
      <nav className="md:hidden flex items-center justify-around bg-slate-950 border-t border-slate-800/80 py-2 px-1 z-30 shrink-0">
        <button
          onClick={() => setActiveTab('chat')}
          className={`flex flex-col items-center gap-1 p-2 rounded-xl text-[10px] font-medium transition-all ${
            activeTab === 'chat' ? 'text-cyan-400 bg-cyan-500/10' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <MessageSquare className="w-4 h-4" />
          <span>Chat</span>
        </button>

        <button
          onClick={() => setActiveTab('devices')}
          className={`flex flex-col items-center gap-1 p-2 rounded-xl text-[10px] font-medium transition-all ${
            activeTab === 'devices' ? 'text-cyan-400 bg-cyan-500/10' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Laptop className="w-4 h-4" />
          <span>Devices</span>
        </button>

        <button
          onClick={() => setActiveTab('memory')}
          className={`flex flex-col items-center gap-1 p-2 rounded-xl text-[10px] font-medium transition-all ${
            activeTab === 'memory' ? 'text-cyan-400 bg-cyan-500/10' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Brain className="w-4 h-4" />
          <span>Memory</span>
        </button>

        <button
          onClick={() => setActiveTab('mcp')}
          className={`flex flex-col items-center gap-1 p-2 rounded-xl text-[10px] font-medium transition-all ${
            activeTab === 'mcp' ? 'text-cyan-400 bg-cyan-500/10' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Blocks className="w-4 h-4" />
          <span>MCP</span>
        </button>

        <button
          onClick={() => setActiveTab('quantum')}
          className={`flex flex-col items-center gap-1 p-2 rounded-xl text-[10px] font-medium transition-all ${
            activeTab === 'quantum' ? 'text-cyan-400 bg-cyan-500/10' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Atom className="w-4 h-4" />
          <span>Quantum</span>
        </button>
      </nav>
    </main>
  );
}
