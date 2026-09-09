/**
 * R.I.O. TypeScript Client SDK
 */

import { ChatRequest, ChatResponse, ChatStreamChunk, Task, ApprovalDecision } from '../../types';

export class RIOClient {
  private baseUrl: string;
  private wsUrl: string;
  private apiKey?: string;

  constructor(config?: { baseUrl?: string; wsUrl?: string; apiKey?: string }) {
    this.baseUrl = (config?.baseUrl || 'http://localhost:8000').replace(/\/$/, '');
    this.wsUrl = config?.wsUrl || 'ws://localhost:8000/ws';
    this.apiKey = config?.apiKey;
  }

  private get headers(): Record<string, string> {
    const h: Record<string, string> = { 'Content-Type': 'application/json' };
    if (this.apiKey) {
      h['Authorization'] = `Bearer ${this.apiKey}`;
    }
    return h;
  }

  async chat(message: string, sessionId?: string, developerMode = false): Promise<ChatResponse> {
    const payload: ChatRequest = {
      message,
      sessionId,
      inputType: 'text',
      attachments: [],
      developerMode,
    };
    const res = await fetch(`${this.baseUrl}/api/v1/chat`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(`Chat error: ${res.statusText}`);
    }
    return res.json();
  }

  async getTask(taskId: string): Promise<Task> {
    const res = await fetch(`${this.baseUrl}/api/v1/tasks/${taskId}`, {
      headers: this.headers,
    });
    if (!res.ok) {
      throw new Error(`Failed to fetch task: ${res.statusText}`);
    }
    return res.json();
  }

  async submitApproval(requestId: string, approved: boolean, reason?: string): Promise<boolean> {
    const payload: ApprovalDecision = {
      requestId,
      decision: approved ? 'approved' : 'denied',
      reason,
    };
    const res = await fetch(`${this.baseUrl}/api/v1/approvals/${requestId}`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify(payload),
    });
    return res.ok;
  }
}
