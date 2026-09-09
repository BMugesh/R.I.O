"""Planner Agent for R.I.O."""

from typing import Any, Dict
from agents.base import BaseAgent
from packages.schemas.agents import AgentManifest, AgentResult, AgentRiskLevel, AgentStatus
from packages.schemas.input import InputType, RIOInput


class PlannerAgent(BaseAgent):
    """Deconstructs high-level user tasks into formal DAG task plans."""

    @property
    def manifest(self) -> AgentManifest:
        return AgentManifest(
            id="planner_agent",
            name="Planner Agent",
            description="Deconstructs complex requests into ordered dependency graphs of steps.",
            capabilities=["task_decomposition", "dependency_resolution", "plan_optimization"],
            accepted_input_types=[InputType.TEXT],
            output_types=["structured"],
            risk_level=AgentRiskLevel.LOW,
            supported_models=["openai/gpt-oss-120b"],
        )

    async def run(self, input_data: RIOInput, context: Dict[str, Any]) -> AgentResult:
        goal = input_data.get_text_content()
        # Uses complex_reasoning model (gpt-oss-120b)
        res = await self.model_router.generate(
            task_type="planning",
            messages=[
                {"role": "system", "content": "You are R.I.O. Planner. Break down the user request into logical execution steps."},
                {"role": "user", "content": goal},
            ],
        )
        return AgentResult(status=AgentStatus.SUCCESS, message="Plan generated", data={"plan_summary": res.get("content")})
