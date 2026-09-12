"""Device Router for R.I.O. Core.

Resolves user intent, required capabilities, and target device identities across
the multi-device ecosystem. Dispatches typed DeviceAction envelopes with strict security boundaries.
"""

from dataclasses import dataclass
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from packages.schemas.devices import (
    Device,
    DeviceAction,
    DeviceCapability,
    DeviceResolution,
    DeviceStatus,
    InterfaceType,
    OriginContext,
)
from services.device_registry.registry import DeviceRegistry

logger = logging.getLogger("rio.device_router")

# Strict blacklist of remote execution patterns to enforce security boundary (Part 13)
FORBIDDEN_ACTION_PATTERNS = [
    r"eval\(",
    r"exec\(",
    r"os\.system",
    r"subprocess\.Popen",
    r"__import__",
    r"importlib",
    r"cmd\.exe\s+/c",
    r"powershell\s+-enc",
    r"bash\s+-c",
]


@dataclass
class DeviceRouteResult:
    """Result of device routing analysis."""
    target_device: Optional[Device]
    action: Optional[DeviceAction]
    is_ambiguous: bool = False
    ambiguity_message: Optional[str] = None
    error: Optional[str] = None
    origin_device_id: Optional[str] = None
    execution_device_id: Optional[str] = None
    explicit_override: bool = False
    resolution_reason: str = "default"

    def to_resolution(self) -> DeviceResolution:
        """Convert to Pydantic DeviceResolution model."""
        return DeviceResolution(
            origin_device_id=self.origin_device_id,
            execution_device_id=self.execution_device_id,
            target_device=self.target_device,
            capability=self.action.capability if self.action else None,
            reason=self.resolution_reason,
            explicit_override=self.explicit_override,
            is_ambiguous=self.is_ambiguous,
            ambiguity_message=self.ambiguity_message,
            error=self.error,
        )


class DeviceRouter:
    """Intelligent Multi-Device Intent and Action Router."""

    def __init__(self, registry: Optional[DeviceRegistry] = None):
        self.registry = registry or DeviceRegistry()

    def _detect_security_violations(self, action_type: str, parameters: Dict[str, Any]) -> Optional[str]:
        """Verify that action does not attempt arbitrary remote code execution."""
        serialized = f"{action_type} {str(parameters)}"
        for pat in FORBIDDEN_ACTION_PATTERNS:
            if re.search(pat, serialized, re.IGNORECASE):
                return f"Security Violation: Remote arbitrary code execution pattern '{pat}' is prohibited."
        return None

    def resolve_target_device_from_text(self, text: str) -> Optional[str]:
        """Extract explicit device target keyword or alias from natural language query."""
        text_lower = text.lower()
        if any(k in text_lower for k in ("on my phone", "on phone", "on android", "on mobile", "on pixel", "from phone", "to phone", "on my mobile")):
            return "phone"
        if any(k in text_lower for k in ("on my laptop", "on laptop", "on desktop", "on pc", "on windows", "on workstation", "from laptop", "to laptop", "on my workstation", "on my pc")):
            return "laptop"
        if any(k in text_lower for k in ("on my server", "on server", "on cloud")):
            return "server"
        return None

    def route_action(
        self,
        prompt: str,
        action_type: str,
        parameters: Optional[Dict[str, Any]] = None,
        explicit_device_id: Optional[str] = None,
        origin_context: Optional[OriginContext] = None,
    ) -> DeviceRouteResult:
        """Route an intended action according to 5-tier resolution priority."""
        params = parameters or {}

        # 1. Security Boundary Check
        sec_err = self._detect_security_violations(action_type, params)
        if sec_err:
            logger.error(sec_err)
            return DeviceRouteResult(
                target_device=None,
                action=None,
                error=sec_err,
                resolution_reason="security_violation",
            )

        # 2. Identify required capability
        required_capability = self.map_action_to_capability(action_type)

        origin_dev_id: Optional[str] = None
        if origin_context:
            origin_dev_id = origin_context.origin_device_id

        target_dev: Optional[Device] = None
        explicit_override = False
        resolution_reason = "default"

        # Tier 1: Explicit target device specified in prompt or via explicit_device_id
        target_hint = self.resolve_target_device_from_text(prompt)

        if explicit_device_id:
            target_dev = self.registry.get_device(explicit_device_id)
            if not target_dev:
                target_dev = self.registry.get_device_by_name(explicit_device_id)
            if target_dev:
                explicit_override = True
                resolution_reason = "explicit_user_target"
            else:
                return DeviceRouteResult(
                    target_device=None,
                    action=None,
                    origin_device_id=origin_dev_id,
                    error=f"Explicitly requested device '{explicit_device_id}' not found in registry.",
                    resolution_reason="explicit_device_not_found",
                )
        elif target_hint:
            if target_hint == "phone":
                android_devices = self.registry.get_devices_by_platform("android")
                if android_devices:
                    target_dev = android_devices[0]
            elif target_hint == "laptop":
                desktop_devices = self.registry.get_devices_by_platform("windows")
                if not desktop_devices:
                    desktop_devices = self.registry.get_devices_by_platform("desktop")
                if desktop_devices:
                    target_dev = desktop_devices[0]
            elif target_hint == "server":
                server_devices = self.registry.get_devices_by_platform("server")
                if server_devices:
                    target_dev = server_devices[0]

            if target_dev:
                explicit_override = True
                resolution_reason = "explicit_user_target"
            else:
                return DeviceRouteResult(
                    target_device=None,
                    action=None,
                    origin_device_id=origin_dev_id,
                    error=f"Explicitly requested device type '{target_hint}' not available.",
                    resolution_reason="explicit_device_not_found",
                )

        # Tier 2 & 3: Origin Device Binding from OriginContext (Local Body by Default)
        if not target_dev and origin_context:
            resolved_origin_dev: Optional[Device] = None
            if origin_context.origin_device_id:
                resolved_origin_dev = self.registry.get_device(origin_context.origin_device_id)
                if not resolved_origin_dev:
                    resolved_origin_dev = self.registry.get_device_by_name(origin_context.origin_device_id)

            if not resolved_origin_dev and origin_context.origin_platform:
                plat_devs = self.registry.get_devices_by_platform(origin_context.origin_platform)
                if plat_devs:
                    resolved_origin_dev = plat_devs[0]

            if not resolved_origin_dev and origin_context.interface_type:
                itype = origin_context.interface_type.value if hasattr(origin_context.interface_type, "value") else str(origin_context.interface_type).lower()
                if itype in ("android", "ios", "mobile"):
                    mob_devs = self.registry.get_devices_by_platform("android")
                    if mob_devs:
                        resolved_origin_dev = mob_devs[0]
                elif itype in ("cli", "desktop", "web", "windows"):
                    win_devs = self.registry.get_devices_by_platform("windows") or self.registry.get_devices_by_platform("desktop")
                    if win_devs:
                        resolved_origin_dev = win_devs[0]

            if resolved_origin_dev:
                origin_dev_id = resolved_origin_dev.device_id
                if self._device_has_capability(resolved_origin_dev, required_capability):
                    target_dev = resolved_origin_dev
                    explicit_override = False
                    resolution_reason = "origin_device_binding"
                else:
                    # SAFETY BOUNDARY: Missing capability on origin device fails safely with informative diagnostic.
                    # DO NOT silently redirect to another device without explicit user direction!
                    logger.warning(
                        f"Origin device '{resolved_origin_dev.device_id}' ({resolved_origin_dev.name}) "
                        f"lacks capability '{required_capability}'."
                    )
                    return DeviceRouteResult(
                        target_device=None,
                        action=None,
                        origin_device_id=resolved_origin_dev.device_id,
                        execution_device_id=None,
                        resolution_reason="origin_capability_missing",
                        error=f"Origin device '{resolved_origin_dev.name or resolved_origin_dev.device_id}' does not support required capability '{required_capability}'. To run on another device, please specify explicitly (e.g. 'on my laptop' or 'on my phone').",
                    )

        # Tier 4: Capability-Specific Exclusive Routing (when origin is unknown or unconstrained)
        if not target_dev:
            if required_capability in (
                DeviceCapability.CAMERA_READ.value,
                DeviceCapability.SENSORS_READ.value,
                DeviceCapability.TOUCH_CONTROL.value,
                "camera",
                "camera.read",
            ):
                candidate_devices = self.registry.get_devices_with_capability(required_capability)
                if candidate_devices:
                    target_dev = candidate_devices[0]
                    resolution_reason = "capability_exclusive"
            elif required_capability in (
                DeviceCapability.MOUSE_CONTROL.value,
                DeviceCapability.KEYBOARD_CONTROL.value,
                "mouse.control",
                "keyboard.control",
            ):
                candidate_devices = self.registry.get_devices_with_capability(required_capability)
                if candidate_devices:
                    target_dev = candidate_devices[0]
                    resolution_reason = "capability_exclusive"

        # Tier 5: Ambiguity Detection & Online Fallback (when origin is truly unknown)
        if not target_dev:
            online_devices = self.registry.list_devices(filter_status=DeviceStatus.ONLINE)
            if not online_devices:
                online_devices = self.registry.list_devices()

            matching_capable = [d for d in online_devices if self._device_has_capability(d, required_capability)]

            if len(matching_capable) > 1 and not self.resolve_target_device_from_text(prompt):
                platforms = {d.platform for d in matching_capable}
                if len(platforms) > 1:
                    device_names = " or ".join([f"your {d.name or d.type.value}" for d in matching_capable])
                    return DeviceRouteResult(
                        target_device=None,
                        action=None,
                        is_ambiguous=True,
                        ambiguity_message=f"Do you want to run this on {device_names}?",
                        resolution_reason="ambiguous_multi_device",
                    )
                target_dev = matching_capable[0]
                resolution_reason = "online_capable_match"
            elif len(matching_capable) == 1:
                target_dev = matching_capable[0]
                resolution_reason = "single_capable_match"
            elif online_devices:
                target_dev = online_devices[0]
                resolution_reason = "online_fallback"

        if not target_dev:
            return DeviceRouteResult(
                target_device=None,
                action=None,
                origin_device_id=origin_dev_id,
                error=f"No connected device found supporting capability '{required_capability}'.",
                resolution_reason="no_capable_device",
            )

        # 4. Construct Strongly Typed DeviceAction
        action_obj = DeviceAction(
            device_id=target_dev.device_id,
            capability=required_capability,
            action_type=action_type,
            target=params.get("target") or params.get("app_name") or params.get("package"),
            parameters=params,
            requested_by="rio_core",
        )

        return DeviceRouteResult(
            target_device=target_dev,
            action=action_obj,
            origin_device_id=origin_dev_id or target_dev.device_id,
            execution_device_id=target_dev.device_id,
            explicit_override=explicit_override,
            resolution_reason=resolution_reason,
        )

    def resolve_device(
        self,
        prompt: str,
        action_type: str = "application.launch",
        parameters: Optional[Dict[str, Any]] = None,
        explicit_device_id: Optional[str] = None,
        origin_context: Optional[OriginContext] = None,
    ) -> DeviceResolution:
        """Resolve target device and return typed DeviceResolution model."""
        res = self.route_action(
            prompt=prompt,
            action_type=action_type,
            parameters=parameters,
            explicit_device_id=explicit_device_id,
            origin_context=origin_context,
        )
        return res.to_resolution()

    def map_action_to_capability(self, action: str) -> str:
        """Map action verb to required DeviceCapability identifier."""
        act_clean = action.lower().replace("_", ".")
        if "screenshot" in act_clean or "screen.read" in act_clean or "screen.capture" in act_clean:
            return DeviceCapability.SCREEN_READ.value
        if "screen.record" in act_clean:
            return DeviceCapability.SCREEN_RECORD.value
        if "mouse" in act_clean or "click" in act_clean:
            return DeviceCapability.MOUSE_CONTROL.value
        if "type" in act_clean or "keyboard" in act_clean or "send.message" in act_clean:
            return DeviceCapability.KEYBOARD_CONTROL.value
        if "touch" in act_clean or "tap" in act_clean or "swipe" in act_clean:
            return DeviceCapability.TOUCH_CONTROL.value
        if "open.app" in act_clean or "launch" in act_clean or "application.launch" in act_clean:
            return DeviceCapability.APPLICATION_LAUNCH.value
        if "close.app" in act_clean or "application.close" in act_clean:
            return DeviceCapability.APPLICATION_CLOSE.value
        if "browser" in act_clean:
            return DeviceCapability.BROWSER_CONTROL.value
        if "read.file" in act_clean or "filesystem.read" in act_clean:
            return DeviceCapability.FILESYSTEM_READ.value
        if "write.file" in act_clean or "filesystem.write" in act_clean:
            return DeviceCapability.FILESYSTEM_WRITE.value
        if "photo" in act_clean or "camera" in act_clean:
            return DeviceCapability.CAMERA_READ.value
        if "audio" in act_clean or "mic" in act_clean or "voice" in act_clean:
            return DeviceCapability.MICROPHONE_READ.value
        if "notification" in act_clean:
            return DeviceCapability.NOTIFICATIONS_SEND.value
        if "location" in act_clean:
            return DeviceCapability.LOCATION_READ.value
        if "sensor" in act_clean:
            return DeviceCapability.SENSORS_READ.value
        return DeviceCapability.APPLICATION_LAUNCH.value

    def _device_has_capability(self, device: Device, capability: str) -> bool:
        """Check if device advertises a specific capability."""
        cap_clean = capability.lower().replace("_", ".")
        
        # Canonical capability equivalence groups
        app_launch_group = {"application.launch", "app.launch", "app_launch", "app.management", "app_management", "mobile.control", "mobile_control"}
        screen_group = {"screen.read", "screen.capture", "screen_capture", "screen_read"}
        touch_group = {"touch.control", "touch_control", "touch"}
        mouse_group = {"mouse.control", "mouse_control", "mouse"}
        keyboard_group = {"keyboard.control", "keyboard_control", "keyboard", "text.input", "type.text"}

        if cap_clean in app_launch_group:
            for c in device.capabilities:
                c_str = str(c.value if hasattr(c, "value") else c).lower().replace("_", ".")
                if c_str in app_launch_group or c_str in ("all", "*"):
                    return True
            if device.platform in ("android", "windows", "desktop"):
                return True

        for c in device.capabilities:
            c_str = str(c.value if hasattr(c, "value") else c).lower().replace("_", ".")
            if c_str in ("all", "*") or c_str == cap_clean or cap_clean in c_str or c_str in cap_clean:
                return True
            if cap_clean in screen_group and c_str in screen_group:
                return True
            if cap_clean in touch_group and c_str in touch_group:
                return True
            if cap_clean in mouse_group and c_str in mouse_group:
                return True
            if cap_clean in keyboard_group and c_str in keyboard_group:
                return True

        return False

