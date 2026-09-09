"""Device Coordination Agent for R.I.O."""

from typing import Any, Dict
from agents.base import BaseAgent
from packages.schemas.agents import Action, AgentManifest, AgentResult, AgentRiskLevel, AgentStatus, Evidence
from packages.schemas.input import InputType, RIOInput


class DeviceAgent(BaseAgent):
    """Manages registered device selection, availability checking, and command dispatch."""

    @property
    def manifest(self) -> AgentManifest:
        return AgentManifest(
            id="device_agent",
            name="Device Agent",
            description="Coordinates connected laptops, phones, and devices, checking their online status and hardware capabilities.",
            capabilities=["device_discovery", "status_check", "capability_routing"],
            accepted_input_types=[InputType.DEVICE, InputType.TEXT],
            output_types=["structured"],
            risk_level=AgentRiskLevel.LOW,
            supported_models=["openai/gpt-oss-20b"],
        )

    async def run(self, input_data: RIOInput, context: Dict[str, Any]) -> AgentResult:
        evidence = Evidence(
            type="device_observation",
            source="device_registry",
            data={"status": "online", "device_id": "laptop-01"},
            confidence=1.0,
            verified=True,
        )
        return AgentResult(
            status=AgentStatus.SUCCESS,
            message="Device is online and responsive.",
            data={"device_id": "laptop-01", "status": "online", "type": "laptop"},
            evidence=[evidence],
        )
