"""Device Coordination Agent for R.I.O."""

from typing import Any, Dict, Optional
from agents.base import BaseAgent
from packages.schemas.agents import Action, AgentManifest, AgentResult, AgentRiskLevel, AgentStatus, Evidence
from packages.schemas.devices import DeviceAction
from packages.schemas.input import InputType, RIOInput
from runtime.android.actions import AndroidActionHandler


class DeviceAgent(BaseAgent):
    """Manages registered device selection, availability checking, and command dispatch."""

    def __init__(self, model_router: Optional[Any] = None):
        super().__init__(model_router=model_router)
        self.android_handler = AndroidActionHandler(device_id="android-01")

    @property
    def manifest(self) -> AgentManifest:
        return AgentManifest(
            id="device_agent",
            name="Device Agent",
            description="Coordinates connected laptops, phones, and devices, checking their online status and hardware capabilities.",
            capabilities=["device_discovery", "status_check", "capability_routing", "mobile_control"],
            accepted_input_types=[InputType.DEVICE, InputType.TEXT],
            output_types=["structured"],
            risk_level=AgentRiskLevel.LOW,
            supported_models=["openai/gpt-oss-20b"],
        )

    async def run(self, input_data: RIOInput, context: Dict[str, Any]) -> AgentResult:
        payload = input_data.payload or {}
        if not isinstance(payload, dict):
            payload = {"action_type": str(payload)}

        action_type = payload.get("action_type") or payload.get("action") or "get_device_status"
        device_hint = payload.get("device") or payload.get("target_device") or "laptop"

        # Mobile / Android actions
        if any(k in action_type for k in ("android", "mobile", "touch", "camera", "photo", "location", "sensor")):
            action_obj = DeviceAction(
                device_id="android-01",
                capability="mobile_control",
                action_type=action_type,
                parameters=payload,
                target=payload.get("package") or payload.get("app_name") or payload.get("target"),
            )
            obs = await self.android_handler.execute(action_obj)
            evidence = Evidence(
                type="device_observation",
                source="android_agent",
                data=obs.data or {"action": action_type, "verified": obs.success},
                confidence=1.0 if obs.success else 0.5,
                verified=obs.success,
            )
            return AgentResult(
                status=AgentStatus.SUCCESS if obs.success else AgentStatus.FAILED,
                message=f"Mobile action '{action_type}' executed on phone.",
                data=obs.data or {"action": action_type, "status": obs.status},
                evidence=[evidence],
            )

        # Query real Device Registry status
        from services.device_registry.registry import DeviceRegistry
        registry = DeviceRegistry()
        dev_id = payload.get("device_id") or payload.get("target_device") or payload.get("device") or "laptop-01"
        if dev_id == "laptop":
            dev_id = "laptop-01"
        elif dev_id in ("phone", "android"):
            dev_id = "android-01"

        target_dev = registry.get_device(dev_id) or registry.get_device_by_name(dev_id)
        if target_dev:
            is_online = (target_dev.status.value.lower() == "online" if hasattr(target_dev.status, "value") else str(target_dev.status).lower() == "online")
            obs_data = {
                "device_id": target_dev.device_id,
                "name": target_dev.name,
                "status": "online" if is_online else "offline",
                "type": target_dev.type.value if hasattr(target_dev.type, "value") else str(target_dev.type),
                "platform": target_dev.platform,
                "verified": is_online,
            }
            evidence = Evidence(
                type="device_observation",
                source="device_registry",
                data=obs_data,
                confidence=1.0 if is_online else 0.4,
                verified=is_online,
            )
            return AgentResult(
                status=AgentStatus.SUCCESS if is_online else AgentStatus.FAILED,
                message=f"Device '{target_dev.name}' ({target_dev.device_id}) is {obs_data['status']}.",
                data=obs_data,
                evidence=[evidence],
            )
        else:
            obs_data = {"device_id": dev_id, "status": "unknown", "verified": False}
            evidence = Evidence(
                type="device_observation",
                source="device_registry",
                data=obs_data,
                confidence=0.0,
                verified=False,
            )
            return AgentResult(
                status=AgentStatus.FAILED,
                message=f"Device '{dev_id}' is not registered in Device Registry.",
                data=obs_data,
                evidence=[evidence],
            )

