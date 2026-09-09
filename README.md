# R.I.O. (Reasoning Intelligence Orchestration)
### *Production-Grade Multimodal, Multi-Agent Personal AI Operating System*

> **"Simple on the outside. Extremely structured on the inside."**

R.I.O. is an autonomous personal AI operating system built with a modular multi-agent core, capability-driven model routing, real-time device control, mandatory verification, and an extensible quantum computation layer.

---

## 🏗️ High-Level Architecture

```
USER
  ↓
R.I.O. INTERFACE (Next.js / Voice / WebSockets)
  ↓
INPUT PROCESSOR (Universal Typed Input Envelope)
  ↓
CONTEXT ENGINE (Multi-turn synthesis & working memory)
  ↓
INTENT / TASK UNDERSTANDING (Fast classifier)
  ↓
MEMORY RETRIEVAL (PostgreSQL + pgvector + Redis)
  ↓
PLANNER (Structured DAG task graph generator)
  ↓
AGENT ROUTER (14 Specialized Modular Agents)
  ↓
MODEL ROUTER (Groq: GPT-OSS 120B/20B, Llama 3.3 70B, Llama 3.1 8B, Compound, Whisper)
  ↓
SAFETY / PERMISSION ENGINE (Risk levels & Human Approval Gates)
  ↓
EXECUTION ENGINE (Asynchronous DAG Runner)
  ↓
TOOLS / MCP / DEVICE / QUANTUM
  ↓
OBSERVATION STREAM
  ↓
VERIFICATION ENGINE (Mandatory Multi-Modal Evidence Validation)
  ↓
RETRY / REPLAN (Autonomous Failure Recovery)
  ↓
RESPONSE GENERATOR (Natural Language Synthesis)
  ↓
NATURAL USER RESPONSE
```

---

## ⚡ Quick Start

### 1. Prerequisites
- Python 3.10+
- Node.js 18+ and pnpm / npm
- Docker & Docker Compose (optional, for Postgres + Redis)

### 2. Setup Environment
```bash
cp .env.example .env
# Add your GROQ_API_KEY to .env
```

### 3. Run with Docker Compose
```bash
docker-compose up -d
```
- Web UI: `http://localhost:3000`
- API Gateway & Swagger Docs: `http://localhost:8000/docs`
- Real-time WebSocket: `ws://localhost:8000/ws`

### 4. Run Locally (Development)
**Backend:**
```bash
pip install -e .
uvicorn apps.api.main:app --reload --port 8000
```

**Frontend:**
```bash
cd apps/web
npm install
npm run dev
```

**Desktop Agent (Local Computer Control):**
```bash
python -m apps.desktop_agent.agent
```

---

## 📦 Monorepo Structure

- `apps/web`: Next.js 14+ conversational interface, voice controls, task tickers, and developer DAG inspector.
- `apps/api`: FastAPI ASGI gateway, WebSocket streaming hub, REST endpoints.
- `apps/desktop-agent`: Local client for controlled OS interactions (screen, keyboard, mouse, apps).
- `apps/android-agent`: Android client bridge specification.
- `packages/schemas`: Universal Pydantic schemas (Typed Inputs, Internal Events, Tasks, Tools, Safety, Quantum).
- `packages/protocols`: Strict Python Protocols defining subsystem contracts.
- `packages/types`: Shared TypeScript typings for UI and SDK.
- `services/orchestrator`: Context, Intent, DAG Planner, Execution State Machine, Response Engine.
- `services/model-router`: Capability-based LLM Router (Groq production models + fallbacks).
- `services/memory`: Hybrid memory layer (pgvector embeddings + Redis hot cache + user forgetting).
- `services/safety`: Risk classification (`low`, `medium`, `high`, `critical`) and approval gates.
- `services/tool-router`: Tool registry, sandbox runtime, permissions.
- `services/mcp`: Model Context Protocol standard client, registry, and audit logger.
- `services/verification`: Multi-modal evidence verification engine (DOM, file hashes, API diffs).
- `services/quantum`: Qiskit & Qiskit Aer quantum simulator, QAOA/VQE router.
- `agents/`: 14 modular agents implementing standardized agent interfaces.
- `tests/`: Comprehensive unit, integration, and end-to-end test suite.
