# WebSocket Device Control & Remote Security Specification

---

## 1. Protocol Specification

R.I.O. uses a bi-directional WebSocket interface (`/ws`) for runtime communication.

### Handshake & Registration
When a device connects, it must transmit a registration payload before receiving commands:

```json
{
  "type": "device_register",
  "device_id": "rio-laptop-mugi",
  "device_name": "Mugi Laptop",
  "platform": "windows",
  "platform_version": "Windows 11 (23H2)",
  "runtime_version": "0.2.1-dev",
  "token": "<SECRET_TOKEN>",
  "capabilities": [
    "screen.read",
    "mouse.control",
    "keyboard.control",
    "application.launch"
  ],
  "permissions": [
    "screen.read:true",
    "application.launch:true"
  ],
  "timestamp": "2026-09-09T21:00:00Z"
}
```

Core validates authentication and responds:
```json
{
  "type": "device_registered",
  "device_id": "rio-laptop-mugi",
  "status": "online",
  "timestamp": "2026-09-09T21:00:01Z"
}
```

---

## 2. Typed Command Envelope (`DeviceAction`)

Core dispatches commands exclusively as structured envelopes:

```json
{
  "type": "device_command",
  "command_id": "cmd-4fa9-8b01",
  "device_id": "rio-laptop-mugi",
  "action": "application.launch",
  "parameters": {
    "app_name": "chrome"
  },
  "timeout_seconds": 30.0,
  "timestamp": "2026-09-09T21:00:02Z"
}
```

---

## 3. Observation Return Envelope (`DeviceObservation`)

The runtime replies with structured observations:

```json
{
  "type": "device_observation",
  "device_id": "rio-laptop-mugi",
  "observation": {
    "observation_id": "obs-9981-2210",
    "command_id": "cmd-4fa9-8b01",
    "status": "verified",
    "success": true,
    "action": "application.launch",
    "data": {
      "app": "chrome",
      "process_id": 14208,
      "window_open": true,
      "window_title": "New Tab - Google Chrome",
      "verification_layer": "full_layered"
    },
    "evidence": {
      "process_check": "passed",
      "window_check": "passed"
    },
    "timestamp": "2026-09-09T21:00:04Z"
  }
}
```

---

## 4. Security Boundary & Remote Code Execution Prevention

1. **No Arbitrary Shell / Python Execution**: Direct strings containing `eval()`, `exec()`, `os.system()`, `cmd.exe /c`, `powershell -enc` are rejected by both `DeviceRouter` and local runtimes.
2. **Deny-by-Default Capability Filter**: If a command requests an action whose capability is disabled in `permissions.json`, the supervisor rejects the command and returns an unauthorized observation.
3. **Token Validation**: Devices must provide authentication tokens matching server configuration.
4. **Resilient Reconnection**: Devices follow exponential backoff (1s, 2s, 4s, 8s, 16s... up to 60s max).
