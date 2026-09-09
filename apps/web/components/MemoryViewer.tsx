'use client';

import React, { useState } from 'react';
import { Brain, Trash2, Search, Plus } from 'lucide-react';
import { MemoryItem } from '../../../packages/types';
import { getApiBaseUrl } from '../lib/api';

export const MemoryViewer: React.FC = () => {
  const [query, setQuery] = useState('');
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [topicToForget, setTopicToForget] = useState('');
  const [newFact, setNewFact] = useState('');

  const handleSearch = async () => {
    try {
      const apiBase = getApiBaseUrl();
      const res = await fetch(`${apiBase}/api/v1/memory?query=${encodeURIComponent(query)}`);
      if (res.ok) {
        const data = await res.json();
        setMemories(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleAddMemory = async () => {
    if (!newFact.trim()) return;
    try {
      const apiBase = getApiBaseUrl();
      const res = await fetch(`${apiBase}/api/v1/memory`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: newFact,
          type: 'user_preference',
          importance: 0.8,
          tags: ['manual_entry'],
        }),
      });
      if (res.ok) {
        setNewFact('');
        handleSearch();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleForgetTopic = async () => {
    if (!topicToForget.trim()) return;
    try {
      const apiBase = getApiBaseUrl();
      const res = await fetch(`${apiBase}/api/v1/memory/forget?topic=${encodeURIComponent(topicToForget)}`, {
        method: 'POST',
      });
      if (res.ok) {
        setTopicToForget('');
        handleSearch();
      }
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white">Long-Term Memory & Knowledge</h2>
        <p className="text-xs text-slate-400">pgvector semantic recall and user privacy controls</p>
      </div>

      {/* Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Add Memory */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3">
          <label className="text-xs font-medium text-slate-300">Store Preference or Fact</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={newFact}
              onChange={(e) => setNewFact(e.target.value)}
              placeholder="e.g. My preferred coffee is oat milk latte..."
              className="flex-1 px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500"
            />
            <button
              onClick={handleAddMemory}
              className="px-3 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-medium flex items-center gap-1.5 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" /> Store
            </button>
          </div>
        </div>

        {/* Forget Topic */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3">
          <label className="text-xs font-medium text-rose-400">Forget Topic (Privacy)</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={topicToForget}
              onChange={(e) => setTopicToForget(e.target.value)}
              placeholder="e.g. old project name or private info..."
              className="flex-1 px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-rose-500"
            />
            <button
              onClick={handleForgetTopic}
              className="px-3 py-2 rounded-xl bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-600/30 text-xs font-medium flex items-center gap-1.5 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" /> Forget
            </button>
          </div>
        </div>
      </div>

      {/* Semantic Search */}
      <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Search semantic memory using natural language..."
            className="flex-1 px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500"
          />
          <button
            onClick={handleSearch}
            className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-medium flex items-center gap-2 transition-colors"
          >
            <Search className="w-4 h-4" /> Recall
          </button>
        </div>

        <div className="space-y-2">
          {memories.map((mem) => (
            <div key={mem.id} className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex items-start justify-between gap-4">
              <div className="space-y-1">
                <span className="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 font-mono text-[10px] uppercase">
                  {mem.type}
                </span>
                <p className="text-xs text-slate-200 mt-1">{mem.content}</p>
              </div>
              <span className="text-[10px] font-mono text-slate-500">
                Importance: {(mem.importance * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
