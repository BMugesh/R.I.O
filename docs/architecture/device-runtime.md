# R.I.O. Device Runtime Architecture

---

## 1. Runtime Overview

The R.I.O. Device Runtime is the local background service running on workstations (Windows/Linux/macOS) and mobile devices (Android). It bridges central reasoning with hardware actuators.

---

## 2. Windows Workstation Runtime

### Core Components
- **DeviceManager**: Manages persistent device identity stored at `%APPDATA%\RIO\device_config.json`.
- **PermissionManager**: Manages granular capability permissions stored at `%APPDATA%\RIO\permissions.json`.
- **RuntimeHealth**: Records uptime, heartbeat timestamps, total commands executed, and error diagnostics.
- **RuntimeSupervisor**: Orchestrates background tasks, system tray icons, and event dispatching.
- **WindowsAppValidator**: Implements layered process + window discovery and state verification.

---

## 3. Layered Verification Engine

R.I.O. enforces the rule:
> **Never claim an application is open solely because `subprocess.Popen` succeeded.**

Verification Layers:
1. **Layer 1 — Discovery**: Verifies executable existence via filesystem paths, system PATH, or registry handlers.
2. **Layer 2 — Process Existence**: Checks if process ID is active using `psutil`.
3. **Layer 3 — Top-Level Window Check**: Enumerates visible top-level windows using Windows user32 APIs (`EnumWindows`, `GetWindowTextW`, `GetWindowThreadProcessId`).
4. **Layer 4 — Identity Match**: Confirms window title matches expected application signatures.

If Layer 3 cannot verify a visible window, the runtime honestly reports:
```json
{
  "status": "uncertain",
  "verified": false,
  "error": "Process started, but top-level window could not be verified."
}
```

---

## 4. Capability Matrix & Permissions

| Capability | Default Status | Description |
| :--- | :---: | :--- |
| `screen.read` | **Allowed** | Desktop screen capture |
| `screen.record` | *Denied* | Continuous video recording |
| `mouse.control` | **Allowed** | Mouse click & cursor movement |
| `keyboard.control` | **Allowed** | Keyboard typing & hotkey dispatch |
| `application.launch`| **Allowed** | Process spawn & focus |
| `application.close` | **Allowed** | Clean application termination |
| `browser.control` | **Allowed** | Web navigation & inspection |
| `filesystem.read` | **Allowed** | Sandboxed file reading |
| `filesystem.write` | *Denied* | File creation / modification |
| `microphone.read` | *Denied* | Voice audio recording |
| `camera.read` | *Denied* | Web camera capture |
