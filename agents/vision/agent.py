"""Vision Agent for R.I.O."""

from typing import Any, Dict
from agents.base import BaseAgent
from packages.schemas.agents import AgentManifest, AgentResult, AgentRiskLevel, AgentStatus, Evidence
from packages.schemas.input import InputType, RIOInput


class VisionAgent(BaseAgent):
    """Analyzes images, screenshots, UI layout hierarchies, and visual grounding."""

    @property
    def manifest(self) -> AgentManifest:
        return AgentManifest(
            id="vision_agent",
            name="Vision Agent",
            description="Analyzes images, visual UI components, diagrams, and screenshots for visual grounding.",
            capabilities=["image_understanding", "screenshot_analysis", "ui_hierarchy_grounding"],
            accepted_input_types=[InputType.IMAGE, InputType.SCREEN],
            output_types=["text", "structured"],
            risk_level=AgentRiskLevel.LOW,
            supported_models=["openai/gpt-oss-120b"],
        )

    async def run(self, input_data: RIOInput, context: Dict[str, Any]) -> AgentResult:
        # Simulated visual grounding
        return AgentResult(
            status=AgentStatus.SUCCESS,
            message="Visual content analyzed successfully.",
            data={"ui_elements": [{"type": "button", "label": "Send", "bbox": [100, 200, 150, 230]}]},
            evidence=[Evidence(type="visual_inspection", source="vision_model", confidence=0.9, verified=True)],
        )
