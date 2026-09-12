'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Send, Mic, Paperclip, Terminal, Bot, User, Volume2, Sparkles, Loader2, Smartphone, Laptop } from 'lucide-react';
import { ChatMessage, DeveloperTrace, ApprovalRequest } from '../../../packages/types';
import { TaskTicker } from './TaskTicker';
import { ApprovalModal } from './ApprovalModal';
import { DeveloperDrawer } from './DeveloperDrawer';
import { MarkdownRenderer } from './MarkdownRenderer';
import { getApiBaseUrl } from '../lib/api';

interface ChatViewProps {
  developerMode: boolean;
  onToggleDeveloperMode: () => void;
}

export const ChatView: React.FC<ChatViewProps> = ({ developerMode, onToggleDeveloperMode }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome_msg',
      role: 'assistant',
      content: "Hey! I'm R.I.O. (Reasoning Intelligence Orchestration). How can I help you today?",
      inputType: 'text',
      createdAt: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isExecuting, setIsExecuting] = useState(false);
  const [currentStatus, setCurrentStatus] = useState<string | undefined>();
  const [activeApproval, setActiveApproval] = useState<ApprovalRequest | null>(null);
  const [latestTrace, setLatestTrace] = useState<DeveloperTrace | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [deviceOverride, setDeviceOverride] = useState<'auto' | 'phone' | 'laptop'>('auto');
  const [isMobileDevice, setIsMobileDevice] = useState(false);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const isMob =
        /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
        window.innerWidth <= 768;
      setIsMobileDevice(isMob);
    }
  }, []);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStatus]);

  const handleSend = async () => {
    if (!input.trim() || isExecuting) return;

    const userText = input.trim();
    setInput('');
    const userMsg: ChatMessage = {
      id: String(Date.now()),
      role: 'user',
      content: userText,
      inputType: 'text',
      createdAt: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsExecuting(true);
    setCurrentStatus('Reasoning & planning...');

    const effectiveOrigin =
      deviceOverride === 'phone'
        ? 'android-01'
        : deviceOverride === 'laptop'
        ? 'laptop-01'
        : isMobileDevice
        ? 'android-01'
        : 'laptop-01';
    const effectiveInterface = effectiveOrigin === 'android-01' ? 'mobile' : 'web';

    try {
      const apiBase = getApiBaseUrl();
      const res = await fetch(`${apiBase}/api/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userText,
          sessionId: effectiveOrigin === 'android-01' ? 'mobile_web_session' : 'desktop_web_session',
          originDeviceId: effectiveOrigin,
          interfaceType: effectiveInterface,
          developerMode,
        }),
      });

      if (!res.ok) {
        throw new Error(`Server returned HTTP ${res.status}: ${res.statusText}`);
      }

      const data = await res.json();
      setCurrentStatus(undefined);

      // Assistant Reply
      const botMsg: ChatMessage = {
        id: data.id || String(Date.now() + 1),
        role: 'assistant',
        content: data.reply,
        inputType: 'text',
        createdAt: data.createdAt || new Date().toISOString(),
      };
      setMessages((prev) => [...prev, botMsg]);

      // Developer Trace
      if (data.developerTrace) {
        setLatestTrace(data.developerTrace);
      }
    } catch (err: any) {
      setCurrentStatus(undefined);
      setMessages((prev) => [
        ...prev,
        {
          id: String(Date.now() + 1),
          role: 'assistant',
          content: `I ran into an issue connecting to R.I.O. Core: ${err.message}`,
          inputType: 'text',
          createdAt: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsExecuting(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSend();
  };

  const handleVoiceRecord = async () => {
    if (isRecording) {
      setIsRecording(false);
      setCurrentStatus(undefined);
    } else {
      setIsRecording(true);
      setCurrentStatus('Listening...');
      setTimeout(() => {
        setIsRecording(false);
        setCurrentStatus(undefined);
        setInput("RIO, open WhatsApp and send 'I'll call you tonight' to Arun.");
      }, 2500);
    }
  };

  const handleApprovalDecision = async (requestId: string, approved: boolean) => {
    setActiveApproval(null);
    try {
      const apiBase = getApiBaseUrl();
      await fetch(`${apiBase}/api/v1/approvals/${requestId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requestId,
          decision: approved ? 'approved' : 'denied',
        }),
      });
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="flex flex-col h-full w-full relative overflow-hidden bg-slate-950">
      {/* Top Header */}
      <div className="flex items-center justify-between px-4 sm:px-6 py-3 border-b border-slate-800 bg-slate-950/80 backdrop-blur-md shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-cyan-600 to-blue-500 flex items-center justify-center shadow-lg shadow-cyan-500/20 shrink-0">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-wide flex items-center gap-2">
              R.I.O. <span className="text-[9px] font-mono font-normal px-1.5 py-0.5 rounded-full bg-slate-900 text-cyan-400 border border-slate-800">OS 1.0</span>
            </h1>
            <p className="text-[10px] text-slate-400 hidden xs:block">Reasoning • Intelligence • Orchestration</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Active Device Origin Indicator / Selector */}
          <button
            type="button"
            onClick={() => {
              setDeviceOverride((prev) =>
                prev === 'auto' ? (isMobileDevice ? 'laptop' : 'phone') : prev === 'phone' ? 'laptop' : 'auto'
              );
            }}
            title="Click to toggle default device origin"
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-xs font-mono font-medium border bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700 transition-all"
          >
            {deviceOverride === 'phone' || (deviceOverride === 'auto' && isMobileDevice) ? (
              <>
                <Smartphone className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-emerald-400">Phone</span>
              </>
            ) : (
              <>
                <Laptop className="w-3.5 h-3.5 text-cyan-400" />
                <span className="text-cyan-400">Laptop</span>
              </>
            )}
            {deviceOverride !== 'auto' && <span className="text-[10px] text-amber-400 font-sans font-semibold">(locked)</span>}
          </button>

          {/* Developer Mode Button */}
          <button
            type="button"
            onClick={() => {
              onToggleDeveloperMode();
              if (!developerMode) setIsDrawerOpen(true);
            }}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-xs font-mono font-medium border transition-all ${
              developerMode
                ? 'bg-cyan-500/10 border-cyan-500/40 text-cyan-300 shadow-lg shadow-cyan-500/10'
                : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            <Terminal className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Dev Mode:</span>
            <span>{developerMode ? 'ON' : 'OFF'}</span>
          </button>
        </div>
      </div>

      {/* Messages Feed */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 sm:space-y-6">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-2.5 sm:gap-3 max-w-full sm:max-w-2xl ${
              msg.role === 'user' ? 'ml-auto flex-row-reverse' : 'mr-auto'
            }`}
          >
            <div
              className={`w-7 h-7 sm:w-8 sm:h-8 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${
                msg.role === 'user'
                  ? 'bg-gradient-to-br from-indigo-500 to-purple-600 text-white'
                  : 'bg-slate-900 border border-slate-800 text-cyan-400'
              }`}
            >
              {msg.role === 'user' ? <User className="w-3.5 h-3.5 sm:w-4 sm:h-4" /> : <Bot className="w-3.5 h-3.5 sm:w-4 sm:h-4" />}
            </div>

            <div
              className={`rounded-2xl px-3.5 py-2.5 sm:px-4 sm:py-3 text-sm leading-relaxed shadow-sm break-words max-w-[85%] sm:max-w-none ${
                msg.role === 'user'
                  ? 'bg-cyan-600 text-white rounded-br-none'
                  : 'bg-slate-900/90 text-slate-200 border border-slate-800/80 rounded-bl-none'
              }`}
            >
              <MarkdownRenderer content={msg.content} isUser={msg.role === 'user'} />
            </div>
          </div>
        ))}

        {/* Live Progress Ticker */}
        {currentStatus && (
          <div className="flex justify-start">
            <TaskTicker status={currentStatus} isExecuting={isExecuting} />
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar Form */}
      <div className="p-2.5 sm:p-4 bg-slate-950 border-t border-slate-800/80 shrink-0">
        <form
          onSubmit={handleSubmit}
          className="max-w-3xl mx-auto flex items-center gap-1.5 sm:gap-2 bg-slate-900 border border-slate-800 rounded-2xl p-1.5 sm:p-2 shadow-xl"
        >
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="p-2 sm:p-2.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-xl transition-colors shrink-0"
            title="Attach image or file"
          >
            <Paperclip className="w-4 h-4" />
          </button>
          <input type="file" ref={fileInputRef} className="hidden" />

          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask R.I.O., control apps, or run tasks..."
            className="flex-1 min-w-0 bg-transparent border-none text-base sm:text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none px-2"
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="sentences"
          />

          <button
            type="button"
            onClick={handleVoiceRecord}
            className={`p-2 sm:p-2.5 rounded-xl transition-all shrink-0 ${
              isRecording
                ? 'bg-rose-500 text-white animate-pulse'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
            title="Voice input"
          >
            <Mic className="w-4 h-4" />
          </button>

          <button
            type="submit"
            disabled={!input.trim() || isExecuting}
            className="p-2 sm:p-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-30 text-white shadow-md shadow-cyan-600/20 transition-all shrink-0 flex items-center justify-center min-w-[38px] min-h-[38px]"
            title="Send Message"
          >
            {isExecuting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </form>
      </div>

      {/* Interactive Approval Modal */}
      <ApprovalModal request={activeApproval} onDecision={handleApprovalDecision} />

      {/* Developer Debug Drawer */}
      <DeveloperDrawer
        trace={latestTrace}
        isOpen={developerMode && isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
      />
    </div>
  );
};
