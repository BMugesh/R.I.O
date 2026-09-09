# Milestone 3 — Voice & Wake-Word Interface
**R.I.O. (Reasoning • Intelligence • Orchestration)**
*Status: Complete & Verified*

---

## 1. Architectural Overview

Milestone 3 equips R.I.O. with an always-on, privacy-preserving voice interface enabling natural hands-free command execution while the runtime daemon runs in the background.

```
+-----------------------------------------------------------------------------+
|                            VOICE SUBSYSTEM ARCHITECTURE                     |
+-----------------------------------------------------------------------------+
|                                                                             |
|   [ Microphone Hardware / PCM Stream ]                                      |
|                 │                                                           |
|                 ▼                                                           |
|      [ Permission Check: microphone.read ]                                  |
|                 │ (Allowed)                                                 |
|                 ▼                                                           |
|       [ WakeWordDetector ]  <--- (100% Local Acoustic/Keyword Match)        |
|                 │                                                           |
|         (Wake Detected)                                                     |
|                 ▼                                                           |
|       [ AudioCaptureEngine ] ---> (RMS Energy VAD / Utterance Chunking)     |
|                 │                                                           |
|            (WAV Container)                                                  |
|                 ▼                                                           |
|     [ TranscriptionService ] ---> (Groq Whisper: whisper-large-v3-turbo)    |
|                 │                                                           |
|           (Clean Text)                                                      |
|                 ▼                                                           |
|      [ Unified RIO Orchestrator ] ---> (DAGPlanner -> Agent -> Verification)|
|                 │                                                           |
|                 ▼                                                           |
|       [ Natural Text Response ]                                             |
+-----------------------------------------------------------------------------+
```

---

## 2. Core Subsystem Components

### A. Voice Session State Machine (`voice/session.py`)
Tracks the real-time interaction lifecycle across 7 strictly defined states:
1. **`IDLE`**: Voice listener is uninitialized or paused.
2. **`LISTENING`**: Continuously monitoring local audio for wake-word. **Zero audio is streamed to the cloud.**
3. **`WAKE_DETECTED`**: Trigger phrase detected (`"RIO"`, `"Hey RIO"`, `"FRIDAY"`). Capturing window armed.
4. **`CAPTURING`**: Recording active speech utterance with RMS voice activity detection (VAD) until silence or max duration (10s) is reached.
5. **`TRANSCRIBING`**: Encoding raw PCM samples into in-memory WAV and transcribing via Groq Whisper (`whisper-large-v3-turbo`).
6. **`PROCESSING`**: Forwarding clean command to `RIOOrchestrator` for DAG planning, execution, and verification.
7. **`ERROR`**: Graceful error handling and automatic recovery back to `LISTENING`.

### B. Capability Permission Boundary (`voice/permissions.py`)
- Microphone access is gated behind the `microphone.read` capability.
- **Deny-by-default**: If `microphone.read` is `False`, the audio subsystem refuses to open microphone streams and raises an explicit `PermissionError`.
- Configurable dynamically via CLI: `rio runtime permissions set microphone.read true`.

### C. Local Wake-Word Engine (`voice/wake_word.py`)
- Supported triggers: `["RIO", "Hey RIO", "Hi RIO", "OK RIO", "Hello RIO", "R.I.O.", "FRIDAY"]`.
- 100% local regex and acoustic pattern matcher.
- Automatically isolates and strips the trigger prefix from the user instruction (e.g., `"Hey RIO, open VS Code"` $\rightarrow$ `"open VS Code"`).

### D. Audio Capture & VAD Engine (`voice/audio_capture.py`)
- **Format**: 16,000 Hz, 16-bit Mono PCM (standard for Whisper).
- **RMS Energy Calculation**: Real-time acoustic energy profiling for speech vs. ambient silence.
- **Container**: Automatic in-memory standard RIFF/WAVE encoding via `wave` module.
- **Synthetic Tone Generator**: High-fidelity sine-wave synthesis for deterministic CI/CD and offline verification.

### E. Transcription Service (`voice/transcription.py`)
- Backed by Groq's high-speed Whisper API (`whisper-large-v3-turbo`).
- Validates WAV byte headers.
- Built-in retry and mock provider fallback for offline resilience.

### F. Central Voice Manager (`voice/manager.py`)
- Single-listener concurrency lock (`asyncio.Lock`) preventing race conditions or multiple hardware mic instances.
- Integration with `runtime.event_listener.EventListener` for live telemetry.
- Direct invocation helpers: `execute_voice_command_text()`, `process_audio_bytes()`, `process_audio_chunk()`.

---

## 3. CLI Voice Interaction

Users can interact with the voice interface directly from the CLI:

```bash
# Check voice interface and microphone permission status
rio voice status

# Simulate a voice wake command
rio voice trigger "Hey RIO, open VS Code"
rio voice trigger "FRIDAY, what is 45 * 8?"

# Toggle microphone permissions
rio runtime permissions set microphone.read true
```

---

## 4. Verification & Test Results

- **Total Test Suite**: 49/49 tests passing across all packages.
- **Voice Test Suite (`tests/test_voice.py`)**: 7/7 tests passing:
  - `test_voice_session_state_machine`: Verifies state transitions and telemetry callbacks.
  - `test_voice_permission_gate_enforcement`: Verifies deny-by-default and dynamic permission toggles.
  - `test_local_wake_word_detector`: Verifies 100% local keyword detection and prefix stripping.
  - `test_audio_capture_buffer_and_wav_container`: Verifies RMS energy, silence limits, and WAV generation.
  - `test_transcription_service_mock`: Verifies transcription and fallback.
  - `test_voice_manager_end_to_end_execution`: Verifies end-to-end voice-to-orchestrator pipeline.
  - `test_voice_manager_concurrency_and_cleanup`: Verifies single-listener lock and clean teardown.
- **Frontend Build**: Next.js production build (`apps/web`) succeeds with 0 errors.
