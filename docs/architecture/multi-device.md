# R.I.O. Multi-Device Architecture

**"ONE BRAIN — MANY DEVICES"**

---

## 1. Architectural Overview

R.I.O. (Reasoning • Intelligence • Orchestration) decouples the central intelligence ("The Brain") from hardware and operating-system execution nodes ("The Body").

```text
                         ┌───────────────────┐
                         │    R.I.O. CORE    │
                         │                   │
                         │ Reasoning         │
                         │ Planning / DAG    │
                         │ Memory            │
                         │ Model Router      │
                         │ Safety Engine     │
                         │ Verification      │
                         └─────────┬─────────┘
                                   │
                             Device Router
                                   │
                          Device Registry
                                   │
               ┌───────────────────┼───────────────────┐
               │                   │                   │
               ▼                   ▼                   ▼
        ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
        │   LAPTOP    │     │    PHONE    │     │   SERVER    │
        │             │     │             │     │             │
        │ RIO Runtime │     │ RIO Runtime │     │ RIO Runtime │
        │             │     │             │     │             │
        │ Windows     │     │ Android     │     │ Linux       │
        │ Computer    │     │ Mobile      │     │ Service     │
        │ Agent       │     │ Agent       │     │ Agent       │
        └──────┬──────┘     └──────┬──────┘     └─────────────┘
               │                   │
          Windows OS          Android OS
               │                   │
       ┌───────┼───────┐    ┌──────┼──────────┐
       │       │       │    │      │          │
       ▼       ▼       ▼    ▼      ▼          ▼
     Apps    Screen   I/O  Apps   Screen    Sensors
```

---

## 2. Core Responsibilities vs Device Runtime Responsibilities

### R.I.O. Core
- Natural language intent understanding
- Task decomposition into structured DAGs
- Cross-device orchestration and dependency tracking
- LLM and provider model routing (Groq, OpenAI, Anthropic)
- Short and long-term memory retrieval
- Security policy evaluation and human approval checkpoints
- Layered outcome verification

### Device Runtime (Laptop / Phone / Server)
- Local operating system and process management
- Hardware interaction (Screen, Mouse, Keyboard, Touch, Camera, Microphone)
- Sandboxed filesystem and application lifecycle
- Dual-layer permission enforcement (R.I.O. policy + OS sandbox)
- Process & window telemetry collection
- Structured observation generation

---

## 3. Communication Channel vs Device Access

The WebSocket channel (`ws://` or `wss://`) is exclusively a **nervous system communication bus**. Opening a WebSocket connection does **NOT** grant arbitrary control.

All interactions follow a strict pipeline:

```text
User Intent
    ↓
DAG Step Planning
    ↓
Target Device Resolution (Device Router)
    ↓
Strongly Typed DeviceAction
    ↓
WebSocket Transmission (Authenticated)
    ↓
Local Permission Engine
    ↓
Platform-Specific Agent Execution
    ↓
Layered Evidence Collection
    ↓
Structured DeviceObservation
    ↓
Central Verification Engine
    ↓
Natural User Response
```

---

## 4. Multi-Device Natural Language Experience

R.I.O. enables seamless unified control:
- *"Open Chrome."* → Defaults to active device or queries user if ambiguous.
- *"Open WhatsApp on my phone."* → Directly routes to the Android runtime.
- *"Open VS Code on my laptop."* → Directly routes to the Windows workstation runtime.
- *"Open Chrome on my phone and VS Code on my laptop."* → Generates a multi-device compound DAG and coordinates both devices in parallel/sequence.
