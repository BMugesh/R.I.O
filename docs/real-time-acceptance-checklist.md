# 🔥 R.I.O. Real-Time Device Control & Physical Acceptance Manual

## Master Architecture & Verification Protocol

This document provides the exhaustive, real-time physical acceptance checklist for **R.I.O. (Reasoning • Intelligence • Orchestration)** across **Android Phone**, **Windows Laptop**, and **Interactive CLI**.

---

## 0. Infrastructure & Pre-Flight Checks

### R.I.O. Core Setup
1. Start the R.I.O. Core API:
   ```bash
   python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
   ```
2. Verify Device Registry status:
   ```bash
   python -m apps.cli.main device list
   ```
   *Expected Output*:
   - `laptop-01` (Windows / Workstation) → `ONLINE`
   - `phone-01` (Android / Mobile) → `ONLINE`

---

## 1. 🔌 WebSocket Real-Time Connectivity

Connect both devices to the core daemon:

```text
💻 Laptop Runtime ─────┐
                       │
                       ▼
                   R.I.O. Core
                       ▲
                       │
📱 Android Runtime ────┘
```

### Physical Checks:
- [ ] Connect laptop runtime: `python -m runtime.daemon`
- [ ] Connect Android runtime client: `python -m runtime.android.daemon`
- [ ] Verify both display independent device IDs and independent heartbeats.
- [ ] Disconnect laptop: Phone remains `ONLINE`.
- [ ] Reconnect laptop: Automatically transitions back to `ONLINE` with restored telemetry.

---

## 2. 📱 Phone — Simple App Launch

**Action**: On phone interface, execute:
> **"Open YouTube."**

### Verification:
```text
Origin Device      = PHONE (phone-01)
Execution Device   = PHONE (phone-01)
Action             = android.launch_app
Target Package     = com.google.android.youtube
Verification       = SUCCESS (Activity Resumed)
```
- [ ] YouTube app opens to foreground on the phone screen.
- [ ] R.I.O. confirms: `"Done. YouTube is open."`

---

## 3. 📱 Phone — Multi-Step YouTube Workflow

**Action**: On phone interface, execute:
> **"Open YouTube, search for relaxing music, and play it."**

### Execution DAG:
```text
Step 1: Launch YouTube (android.launch_app)
  ↓
Step 2: Focus Search Field & Type 'relaxing music' (android.search)
  ↓
Step 3: Select Top Result & Start Playback (android.media.play)
  ↓
Step 4: Verify Screen Observation & Audio Stream (verify_app_state)
  ↓
Result: "Done. Playing relaxing music on YouTube."
```

- [ ] Search query is typed into YouTube search.
- [ ] Video playback begins with audio.
- [ ] Final confirmation is delivered ONLY after verification evidence is confirmed.

---

## 4. 📱 Phone — Scheduled Action

**Action**: On phone interface, execute:
> **"Open YouTube, search for relaxing music, and play it at 8:00 PM."**

### Lifecycle:
```text
SCHEDULED ──> WAITING ──> TRIGGERED ──> RUNNING ──> VERIFYING ──> COMPLETED
```
- [ ] Immediately responds: `"Scheduled: '...' for 8:00 PM on your phone."`
- [ ] Task persists to disk (`data/scheduled_tasks.json`) and survives Core restarts.
- [ ] At scheduled trigger time, scheduler wakes, dispatches the DAG to the phone, and verifies completion.

---

## 5. 💻 Laptop — YouTube Browser Workflow

**Action**: On laptop interface / desktop app, execute:
> **"Open YouTube, search for relaxing music, and play it."**

### Verification:
- [ ] Google Chrome / default browser opens to YouTube search query.
- [ ] Top video is selected and media player DOM enters `PLAYING` state.
- [ ] Phone remains completely unaffected (Origin binding defaults to laptop).

---

## 6. 🖥️ CLI — Local Computer Execution

Run in terminal:
```bash
# App & Web test
rio "open YouTube and search for relaxing music"

# Screenshot capture
rio "take a screenshot"
```

### Verification:
- [ ] CLI executes on the host computer without prompting *"Which device?"*.
- [ ] Screenshot file is saved under `screenshots/` and verified.

---

## 7. 📱 → 💻 Phone to Laptop Explicit Remote Control

From **Phone**, execute:
> **"Open VS Code on my laptop."**

### Verification:
```text
Origin Device      = PHONE (phone-01)
Explicit Target    = LAPTOP (laptop-01)
Execution Device   = LAPTOP (laptop-01)
Resolution Reason  = Explicit target device requested
```
- [ ] Visual Studio Code launches on the Windows laptop.
- [ ] Phone screen remains untouched.
- [ ] Phone receives confirmation: `"Done. VS Code is open on your laptop."`

---

## 8. 💻 → 📱 Laptop to Phone Explicit Remote Control

From **Laptop**, execute:
> **"Open YouTube on my phone."**

### Verification:
- [ ] YouTube launches on physical phone screen.
- [ ] Laptop displays confirmation: `"Done. YouTube is open on your phone."`

---

## 9. 🚨 Negative Safety Test (No Silent Redirection)

From **Phone**, execute:
> **"Open VS Code."**

### Safety Law Enforced:
Because VS Code is a desktop-only application and the origin is mobile without an explicit target:
- [ ] R.I.O. **MUST NOT** secretly execute VS Code on the laptop.
- [ ] R.I.O. responds safely:
  > *"Origin device 'phone-01' (Android) does not support desktop application 'Vs Code'. To run on your laptop, please specify 'Open Vs Code on my laptop'."*

---

## 10. 🔐 Capability Permission Enforcement

1. Revoke permission:
   ```bash
   rio runtime permissions set application.launch false
   ```
2. Request: `"Open YouTube."`
   - [ ] Execution is **BLOCKED** with permission denied error.
3. Re-enable permission:
   ```bash
   rio runtime permissions set application.launch true
   ```
   - [ ] Execution succeeds normally.

---

## 11. 🌐 Connection Failure & 12. 👀 Evidence Verification

- [ ] If a device disconnects mid-flight, R.I.O. flags the step as unverified / failed.
- [ ] **Architectural Rule**: *"No evidence = No success."* Fake success strings are strictly forbidden.

---

## 13. 🧠 Multi-Step Web Research & Document Summary

**Action**:
> **"Open Chrome, search for the latest Razorpay documentation, open the relevant result, and summarize it."**

- [ ] Step 1: Navigates Chrome to search query.
- [ ] Step 2: Fetches documentation pages.
- [ ] Step 3: Document Agent synthesizes structured markdown summary.
- [ ] Step 4: Verification confirms summary completeness.

---

## 14 & 15. Device Control Matrices

### Phone Matrix (12 Capabilities)
| Capability | Action Type | Verified Observation |
| :--- | :--- | :--- |
| Open YouTube | `application.launch` | Activity Resumed |
| Open Chrome | `application.launch` | Activity Resumed |
| Open WhatsApp | `application.launch` | Activity Resumed |
| Search YouTube | `android.search` | Results Rendered |
| Play Media | `android.media.play` | Audio Output Active |
| Capture Screen | `screen.capture` | PNG Frame Valid |
| Touch Tap | `touch.tap` | Coordinates Tapped |
| Touch Swipe | `touch.swipe` | Scroll Dispatched |
| Text Input | `text.input` | Text Rendered in Input |
| Notifications | `notification.send` | System Notification Posted |
| Camera Capture | `camera.capture` | Photo Stored to DCIM |
| Microphone Record | `microphone.capture` | Audio Stored to Media |

### Laptop Matrix (11 Capabilities)
| Capability | Action Type | Verified Observation |
| :--- | :--- | :--- |
| Open Chrome | `open_application` | Window Enum & PID Match |
| Open VS Code | `open_application` | Window Enum & PID Match |
| Open Notepad | `open_application` | Window Enum & PID Match |
| Open Calculator | `open_application` | Window Enum & PID Match |
| Screenshot | `screenshot` | PNG Exists & Dimension Match |
| Mouse Click | `mouse_click` | OS Cursor Event Dispatched |
| Keyboard Input | `type_text` | OS Keyboard Event Dispatched |
| Browser Nav | `browser_navigate` | DOM Body / Video Query |
| Search Video | `play_video` | DOM Video Playing |
| Close App | `close_application` | Process Terminated |
| Screen Record | `screen_record` | Video Container Valid |

---

## 16. CLI Acceptance Checklist Command

Run the complete real-time acceptance check directly in terminal:
```bash
rio test
# or
rio checklist
```

This runs all 20 sections in sequence and prints the verified visual checklist matrix.
