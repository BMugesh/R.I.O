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

## ⚡ Quick Start (Single Command)

### 1. Prerequisites & Environment
```bash
cp .env.example .env
# Add your GROQ_API_KEY to .env
```

### 2. Launch Everything with 1 Command
Run the unified multi-process supervisor that launches the FastAPI Gateway, Laptop Background Runtime, Android Bridge, and Next.js Web UI simultaneously:

```bash
python start_rio.py
```
*or via the R.I.O. CLI / batch scripts:*
```bash
rio start                  # CLI unified start
rio start --cli            # Start all services + launch interactive CLI shell
./start.bat                # Windows CMD launcher
./start.ps1                # Windows PowerShell launcher
```

### 3. Service Access Points
- 💻 **Web UI (Local Workstation):** `http://localhost:3000`
- 📱 **Web UI (Mobile / Wi-Fi):** `http://<your-local-ip>:3000`
- 📚 **Core API & Swagger Docs:** `http://localhost:8000/docs`
- 🔌 **WebSocket Hub:** `ws://localhost:8000/ws`

---

## 🛠️ Individual Service Execution (Manual)
If you prefer running services independently in separate terminals:

**1. Backend Core Gateway:**
```bash
python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
```

**2. Laptop Background Runtime Daemon:**
```bash
python -m runtime.daemon
```

**3. Android Runtime Bridge Daemon:**
```bash
python -m runtime.android.daemon
```

**4. Next.js Web Frontend:**
```bash
cd apps/web && npm run dev
```

**5. Interactive CLI:**
```bash
rio
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
