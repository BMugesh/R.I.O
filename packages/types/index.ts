/**
 * Universal TypeScript Type Definitions for R.I.O.
 */

export type InputType =
  | 'text'
  | 'voice'
  | 'image'
  | 'video'
  | 'screen'
  | 'document'
  | 'sensor'
  | 'location'
  | 'event'
  | 'device'
  | 'gesture'
  | 'tool_result'
  | 'memory_context';

export interface InputMetadata {
  clientId?: string;
  sessionId?: string;
  userId?: string;
  deviceId?: string;
  mimeType?: string;
  fileName?: string;
  fileSizeBytes?: number;
  language?: string;
  coordinates?: { x: number; y: number };
  deviceType?: string;
  custom?: Record<string, unknown>;
}

export interface RIOInput {
  id: string;
  type: InputType;
  timestamp: string;
  source: string;
  payload: unknown;
  metadata?: InputMetadata;
}

export type EventType =
  | 'user_message'
  | 'assistant_message'
  | 'task_created'
  | 'task_planned'
  | 'agent_selected'
  | 'model_selected'
  | 'tool_requested'
  | 'tool_result'
  | 'device_command'
  | 'device_observation'
  | 'approval_requested'
  | 'approval_granted'
  | 'approval_denied'
  | 'verification_started'
  | 'verification_success'
  | 'verification_failed'
  | 'task_completed'
  | 'task_failed'
  | 'task_retry'
  | 'quantum_job'
  | 'quantum_result';

export interface RIOEvent {
  id: string;
  type: EventType;
  timestamp: string;
  taskId?: string;
  stepId?: string;
  traceId?: string;
  agentId?: string;
  modelId?: string;
  deviceId?: string;
  toolId?: string;
  payload: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

export type AgentStatus = 'success' | 'failed' | 'needs_approval' | 'partial' | 'uncertain';
export type AgentRiskLevel = 'low' | 'medium' | 'high' | 'critical';

export interface Action {
  actionType: string;
  target?: string;
  parameters: Record<string, unknown>;
  riskLevel: AgentRiskLevel;
  description: string;
}

export interface Evidence {
  type: string;
  source: string;
  data: unknown;
  confidence: number;
  verified: boolean;
  timestamp?: string;
}

export interface AgentResult {
  status: AgentStatus;
  message?: string;
  data?: unknown;
  actions?: Action[];
  evidence?: Evidence[];
  metadata?: Record<string, unknown>;
}

export interface AgentManifest {
  id: string;
  name: string;
  description: string;
  capabilities: string[];
  acceptedInputTypes: InputType[];
  outputTypes: string[];
  requiredTools: string[];
  riskLevel: AgentRiskLevel;
  supportedModels: string[];
  isActive: boolean;
}

export type TaskStatus =
  | 'pending'
  | 'planning'
  | 'running'
  | 'waiting_approval'
  | 'completed'
  | 'failed'
  | 'retrying'
  | 'cancelled';

export type StepStatus =
  | 'pending'
  | 'running'
  | 'waiting_approval'
  | 'completed'
  | 'failed'
  | 'skipped'
  | 'verifying';

export interface VerificationStrategy {
  strategyType: string;
  expectedState: Record<string, unknown>;
  timeoutSeconds: number;
  retryCount: number;
  isMandatory: boolean;
}

export interface TaskStep {
  id: string;
  taskId?: string;
  name: string;
  description: string;
  agentId: string;
  action: Action;
  dependencies: string[];
  status: StepStatus;
  riskLevel: AgentRiskLevel;
  requiresApproval: boolean;
  verificationStrategy?: VerificationStrategy;
  observation?: Record<string, unknown>;
  evidence: Evidence[];
  result?: unknown;
  error?: string;
  retryCount: number;
  maxRetries: number;
  startedAt?: string;
  completedAt?: string;
}

export interface TaskPlan {
  id: string;
  goal: string;
  steps: TaskStep[];
  estimatedDurationSeconds: number;
  isApproved: boolean;
  createdAt: string;
}

export interface Task {
  id: string;
  sessionId?: string;
  userId?: string;
  goal: string;
  status: TaskStatus;
  plan?: TaskPlan;
  riskLevel: AgentRiskLevel;
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
  error?: string;
  finalResponse?: string;
  metadata: Record<string, unknown>;
}

export type ApprovalStatus = 'pending' | 'approved' | 'denied' | 'expired';

export interface ApprovalRequest {
  id: string;
  taskId: string;
  stepId?: string;
  actionType: string;
  target?: string;
  parameters: Record<string, unknown>;
  description: string;
  riskLevel: AgentRiskLevel;
  status: ApprovalStatus;
  requestedAt: string;
  resolvedAt?: string;
  resolvedBy?: string;
  decisionReason?: string;
  timeoutSeconds: number;
}

export interface DeveloperTrace {
  taskId?: string;
  agentId?: string;
  modelId?: string;
  plan?: TaskPlan;
  steps: TaskStep[];
  events: Record<string, unknown>[];
  verificationSummary?: Record<string, unknown>;
  latencyMs: number;
}

export interface ChatMessage {
  id: string;
  sessionId?: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  inputType: InputType;
  attachments?: Record<string, unknown>[];
  createdAt: string;
}

export interface ChatResponse {
  id: string;
  sessionId: string;
  reply: string;
  taskId?: string;
  status: string;
  pendingApproval?: ApprovalRequest;
  developerTrace?: DeveloperTrace;
  createdAt: string;
}

export interface ChatStreamChunk {
  chunkType: 'token' | 'status_update' | 'approval_required' | 'done' | 'error';
  content?: string;
  taskStatus?: string;
  approval?: ApprovalRequest;
  developerTrace?: DeveloperTrace;
}

export interface Device {
  deviceId: string;
  name: string;
  type: 'laptop' | 'desktop' | 'android' | 'ios' | 'server' | 'custom';
  status: 'online' | 'offline' | 'busy' | 'error';
  capabilities: string[];
  permissions: string[];
  ipAddress?: string;
  osInfo?: string;
  lastSeen: string;
  metadata: Record<string, unknown>;
}

export interface QuantumJob {
  id: string;
  algorithm: 'qaoa' | 'vqe' | 'max_cut' | 'portfolio_optimization' | 'qml_classification' | 'circuit_execution' | 'grover_search';
  backend: 'aer_simulator' | 'statevector_simulator' | 'ibm_quantum' | 'mock_quantum';
  circuitSpec?: Record<string, unknown>;
  problemMatrix?: number[][];
  status: 'pending' | 'running' | 'completed' | 'failed';
  result?: Record<string, unknown>;
  error?: string;
  createdAt: string;
  completedAt?: string;
}

export interface ToolDefinition {
  id: string;
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  requiredPermissions: string[];
  riskLevel: AgentRiskLevel;
  providerType: 'builtin' | 'mcp' | 'device' | 'plugin' | 'rest';
  providerId?: string;
  isSandboxed: boolean;
  enabled: boolean;
}

export interface MCPManifest {
  id: string;
  name: string;
  version: string;
  transport: 'stdio' | 'sse';
  command?: string;
  args: string[];
  url?: string;
  headers: Record<string, string>;
  tools: ToolDefinition[];
  isActive: boolean;
}

export interface MemoryItem {
  id: string;
  userId?: string;
  type: 'short_term' | 'conversation' | 'task' | 'semantic' | 'episodic' | 'device_state' | 'user_preference';
  content: string;
  importance: number;
  tags: string[];
  metadata: Record<string, unknown>;
  createdAt: string;
  lastAccessed: string;
}
