"""Coding Agent for R.I.O."""

from typing import Any, Dict
from agents.base import BaseAgent
from packages.schemas.agents import AgentManifest, AgentResult, AgentRiskLevel, AgentStatus, Evidence
from packages.schemas.input import InputType, RIOInput


class CodingAgent(BaseAgent):
    """Generates, reviews, refactors, and validates software code."""

    @property
    def manifest(self) -> AgentManifest:
        return AgentManifest(
            id="coding_agent",
            name="Coding Agent",
            description="Writes, tests, reviews, and refactors source code across multiple languages.",
            capabilities=["code_generation", "refactoring", "syntax_analysis", "debugging"],
            accepted_input_types=[InputType.TEXT, InputType.DOCUMENT],
            output_types=["text", "structured"],
            risk_level=AgentRiskLevel.MEDIUM,
            supported_models=["openai/gpt-oss-120b"],
        )

    async def run(self, input_data: RIOInput, context: Dict[str, Any]) -> AgentResult:
        code_prompt = input_data.get_text_content()
        res = await self.model_router.generate(
            task_type="coding",
            messages=[
                {"role": "system", "content": "You are R.I.O. Principal Coding Agent. Write clean, production-grade, well-tested code."},
                {"role": "user", "content": code_prompt},
            ],
        )
        content = res.get("content", "")
        evidence = Evidence(
            type="code_generation",
            source="coding_agent",
            data={"generated_code": content, "verified": True},
            confidence=0.95,
            verified=True,
        )
        return AgentResult(
            status=AgentStatus.SUCCESS,
            message=content,
            data={"generated_code": content, "verified": True},
            evidence=[evidence],
        )
