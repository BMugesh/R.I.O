"""Document Agent for R.I.O."""

from typing import Any, Dict
from agents.base import BaseAgent
from packages.schemas.agents import AgentManifest, AgentResult, AgentRiskLevel, AgentStatus
from packages.schemas.input import InputType, RIOInput


class DocumentAgent(BaseAgent):
    """Processes, extracts, and summarizes document files (PDF, Markdown, Docx, Text)."""

    @property
    def manifest(self) -> AgentManifest:
        return AgentManifest(
            id="document_agent",
            name="Document Agent",
            description="Parses, extracts, and analyzes document content and reports.",
            capabilities=["document_parsing", "qa_extraction", "summarization"],
            accepted_input_types=[InputType.DOCUMENT, InputType.TEXT],
            output_types=["text", "structured"],
            risk_level=AgentRiskLevel.LOW,
            supported_models=["llama-3.3-70b-versatile"],
        )

    async def run(self, input_data: RIOInput, context: Dict[str, Any]) -> AgentResult:
        doc_text = input_data.get_text_content()
        res = await self.model_router.generate(
            task_type="summarization",
            messages=[
                {"role": "system", "content": "You are R.I.O. Document Agent. Extract key insights and structured summaries."},
                {"role": "user", "content": doc_text},
            ],
        )
        return AgentResult(status=AgentStatus.SUCCESS, message=res.get("content", ""), data={"summary": res.get("content")})
