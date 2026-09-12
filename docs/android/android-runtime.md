# R.I.O. Android Runtime Architecture

---

## 1. Overview

The R.I.O. Android Runtime is a dedicated mobile execution bridge connecting Android devices (smartphones, tablets) to R.I.O. Core over secure WebSockets.

---

## 2. Access Levels

R.I.O. defines 5 progressive levels of Android mobile automation:

```text
Level 1: Application Launch
         (Open Chrome, WhatsApp, Spotify, Settings)
    ↓
Level 2: Basic UI Interaction
         (Tap, Swipe, Scroll, Text Input)
    ↓
Level 3: Screen Understanding
         (Screen Capture, UI Hierarchy Inspection)
    ↓
Level 4: Application-Specific Control
         (App-Specific Intent APIs and Data Extraction)
    ↓
Level 5: Autonomous GUI Agent
         (See → Understand → Plan → Touch → Observe → Verify)
```

---

## 3. Dual-Layer Permission Model

Android capability execution requires agreement between two independent security layers:

```text
       R.I.O. Capability Policy (permissions.json)
                         +
         Android OS System Permissions
                         =
               CAPABILITY AVAILABLE
```

If either layer denies authorization, the action is rejected immediately with an informative reason.

### Supported Android Capabilities:
- `screen.read`: Requires `android.permission.MEDIA_PROJECTION`
- `touch.control`: Requires `android.permission.BIND_ACCESSIBILITY_SERVICE`
- `application.launch`: Requires standard intent dispatch
- `camera.read`: Requires `android.permission.CAMERA`
- `microphone.read`: Requires `android.permission.RECORD_AUDIO`
- `notifications.read`: Requires `android.permission.BIND_NOTIFICATION_LISTENER_SERVICE`
- `notifications.send`: Requires `android.permission.POST_NOTIFICATIONS`
- `location.read`: Requires `android.permission.ACCESS_FINE_LOCATION`
- `sensors.read`: Requires `android.permission.BODY_SENSORS`

---

## 4. Connection Lifecycle

Android devices transition through explicit lifecycle states:
- `CONNECTING`
- `CONNECTED`
- `AUTHENTICATED`
- `REGISTERED`
- `ONLINE`
- `DISCONNECTED`
- `RECONNECTING` (Exponential backoff: 1s, 2s, 4s... max 60s)
- `STOPPED`

---

## 5. Telemetry & Heartbeat

The Android runtime periodically transmits health telemetry:
- Device identity (`rio-phone-xxxx`)
- Connection state (`ONLINE`)
- Battery level & charging state
- Uptime
- Active capabilities
- Error counts
