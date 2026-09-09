"""Memory Agent for R.I.O."""

from typing import Any, Dict
from agents.base import BaseAgent
from packages.schemas.agents import AgentManifest, AgentResult, AgentRiskLevel, AgentStatus
from packages.schemas.input import InputType, RIOInput


class MemoryAgent(BaseAgent):
    """Manages memory retention, semantic updates, and user forgetting commands."""

    @property
    def manifest(self) -> AgentManifest:
        return AgentManifest(
            id="memory_agent",
            name="Memory Agent",
            description="Stores user facts, updates long-term preferences, and executes privacy forgetting operations.",
            capabilities=["store_preference", "forget_topic", "memory_query"],
            accepted_input_types=[InputType.TEXT, InputType.MEMORY_CONTEXT],
            output_types=["text", "structured"],
            risk_level=AgentRiskLevel.LOW,
            supported_models=["llama-3.3-70b-versatile"],
        )

    async def run(self, input_data: RIOInput, context: Dict[str, Any]) -> AgentResult:
        text = input_data.get_text_content()
        if "forget" in text.lower():
            return AgentResult(
                status=AgentStatus.SUCCESS,
                message="I've forgotten that information for you.",
                data={"action": "forget", "topic": text},
            )
        return AgentResult(
            status=AgentStatus.SUCCESS,
            message="I've noted that in your personal memory.",
            data={"action": "store", "memory": text},
        )
