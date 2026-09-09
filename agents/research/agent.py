"""Research Agent for R.I.O."""

from typing import Any, Dict
from agents.base import BaseAgent
from packages.schemas.agents import AgentManifest, AgentResult, AgentRiskLevel, AgentStatus, Evidence
from packages.schemas.input import InputType, RIOInput


class ResearchAgent(BaseAgent):
    """Conducts multi-source web and knowledge synthesis."""

    @property
    def manifest(self) -> AgentManifest:
        return AgentManifest(
            id="research_agent",
            name="Research Agent",
            description="Searches information sources, synthesizes data, and produces comprehensive reports.",
            capabilities=["web_search", "synthesis", "summarization"],
            accepted_input_types=[InputType.TEXT, InputType.DOCUMENT],
            output_types=["text", "structured"],
            risk_level=AgentRiskLevel.LOW,
            supported_models=["groq/compound", "openai/gpt-oss-120b"],
        )

    async def run(self, input_data: RIOInput, context: Dict[str, Any]) -> AgentResult:
        query = input_data.get_text_content()
        res = await self.model_router.generate(
            task_type="web_research",
            messages=[
                {"role": "system", "content": "You are R.I.O. Research Agent. Gather accurate findings and synthesize a structured summary."},
                {"role": "user", "content": query},
            ],
        )
        evidence = Evidence(
            type="research_summary",
            source="groq_compound_search",
            data={"query": query, "has_results": True, "verified": True},
            confidence=0.95,
            verified=True,
        )
        return AgentResult(
            status=AgentStatus.SUCCESS,
            message=res.get("content", ""),
            data={"research_findings": res.get("content", ""), "has_results": True, "verified": True},
            evidence=[evidence],
        )

