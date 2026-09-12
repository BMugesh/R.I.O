# R.I.O. — Origin Device Binding & Local Execution

## 1. Core Architectural Principle

```text
ONE BRAIN — LOCAL BODY BY DEFAULT — REMOTE BODY ONLY WHEN EXPLICITLY REQUESTED
```

In R.I.O. (Reasoning • Intelligence • Orchestration), the interface, runtime, or session from which the user issues a command binds the **Origin Context** (`OriginContext`) and determines the default execution target:

* **Phone Origin** (e.g. Android mobile app / touch): *"Open WhatsApp"* → Executes on the connected Phone (`phone-01` / Android runtime).
* **Laptop / Workstation Origin** (e.g. Windows desktop runtime): *"Open WhatsApp"* → Executes on the local Laptop (`laptop-01` / Windows runtime).
* **CLI Origin** (`rio "Open WhatsApp"`): Defaults to the local workstation without asking *"Which device?"*.
* **Explicit Remote Override**: *"Open WhatsApp on my phone"* from a Laptop → Routes to the Phone (`phone-01`).
* **Safety Boundary (No Silent Redirection)**: *"Open VS Code"* from Phone without mentioning Laptop → Fails safely with an informative diagnostic message rather than silently executing on another device without user permission.

---

## 2. 5-Tier Device Resolution Flow

```text
                               ┌─────────────────────────┐
                               │   User Input / Intent   │
                               └────────────┬────────────┘
                                            │
                                            ▼
                          ┌───────────────────────────────────┐
                          │   Device Router Resolution Layer  │
                          └─────────────────┬─────────────────┘
                                            │
          ┌─────────────────────────────────┼─────────────────────────────────┐
          │                                 │                                 │
          ▼                                 ▼                                 ▼
   [Tier 1: Explicit]             [Tier 2/3: Origin Context]          [Tier 4/5: Fallback]
  "on my phone" /                origin_device_id /                  Unknown origin ->
  "on my laptop" /               origin_platform /                   Capability-exclusive or
  explicit_device_id             interface_type                      ambiguity prompt only
          │                                 │                                 │
          ▼                                 ▼                                 ▼
  Explicit Remote Target          Local Origin Device Target          Single Online Match
```

### Resolution Priority Matrix

1. **Priority 1 (Explicit User Directive)**:
   * Keywords such as `"on my phone"`, `"on my laptop"`, `"from phone"`, or explicit `deviceId` parameters override any session defaults.
   * `explicit_override = True`, `resolution_reason = "explicit_user_target"`.

2. **Priority 2 & 3 (Origin Context Binding)**:
   * If `OriginContext` contains `origin_device_id` (e.g. `"phone-01"`, `"laptop-01"`), `origin_platform`, or `interface_type` (`"android"`, `"cli"`, `"desktop"`, `"web"`), R.I.O. checks if the origin device supports the required capability.
   * If capable: `explicit_override = False`, `resolution_reason = "origin_device_binding"`.
   * **Missing Capability Safety Protection**: If the origin device lacks the capability (e.g. desktop-only IDE on Android), R.I.O. returns a clear diagnostic and suggests specifying the explicit remote device. **No silent redirection occurs.**

3. **Priority 4 (Capability-Exclusive Routing)**:
   * If origin is unconstrained, hardware-specific actions (e.g. `camera.capture`, `sensors.read` → Android; `mouse.control`, `keyboard.control` → Windows) route to capable devices.

4. **Priority 5 (Ambiguity Detection)**:
   * Only triggered when origin is unknown and multiple devices across differing platforms support the action.
   * Returns: `"Do you want to run this on your laptop or your phone?"`.

---

## 3. Schemas & Data Structures

### `OriginContext` (`packages/schemas/devices.py`)
```python
class OriginContext(BaseModel):
    session_id: str = "default_session"
    interface_type: Union[InterfaceType, str] = InterfaceType.CLI
    origin_device_id: Optional[str] = None
    origin_device_type: Optional[Union[DeviceType, str]] = None
    origin_platform: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### `DeviceResolution` (`packages/schemas/devices.py`)
```python
class DeviceResolution(BaseModel):
    origin_device_id: Optional[str] = None
    execution_device_id: Optional[str] = None
    target_device: Optional[Device] = None
    capability: Optional[str] = None
    reason: str = "default"
    explicit_override: bool = False
    is_ambiguous: bool = False
    ambiguity_message: Optional[str] = None
    error: Optional[str] = None
```

---

## 4. API and WebSocket Usage

### REST API (`POST /api/v1/chat`)
```json
{
  "message": "Open WhatsApp",
  "sessionId": "session_android_101",
  "interfaceType": "android",
  "originDeviceId": "phone-01",
  "developerMode": true
}
```

### Response
```json
{
  "sessionId": "session_android_101",
  "reply": "Done. WhatsApp is open.",
  "status": "completed",
  "developerTrace": {
    "origin_device_id": "phone-01",
    "execution_device_id": "phone-01",
    "resolution_reason": "origin_device_binding",
    "explicit_override": false,
    "steps": [...]
  }
}
```
