"""Conversation Agent for R.I.O."""

from typing import Any, Dict
from agents.base import BaseAgent
from packages.schemas.agents import AgentManifest, AgentResult, AgentRiskLevel, AgentStatus
from packages.schemas.input import InputType, RIOInput


class ConversationAgent(BaseAgent):
    """Handles general conversational interaction, chit-chat, and natural explanations."""

    @property
    def manifest(self) -> AgentManifest:
        return AgentManifest(
            id="conversation_agent",
            name="Conversation Agent",
            description="Manages natural conversation, question answering, and friendly user dialogues.",
            capabilities=["chit_chat", "general_qa", "dialogue_management"],
            accepted_input_types=[InputType.TEXT, InputType.VOICE],
            output_types=["text"],
            risk_level=AgentRiskLevel.LOW,
            supported_models=["llama-3.3-70b-versatile", "openai/gpt-oss-120b"],
        )

    async def run(self, input_data: RIOInput, context: Dict[str, Any]) -> AgentResult:
        user_text = input_data.get_text_content()
        recent_turns = context.get("recent_turns", [])
        messages = [
            {"role": "system", "content": "You are R.I.O., a helpful and conversational AI assistant. Keep responses natural, clear, and concise."},
            *[{"role": t["role"], "content": t["content"]} for t in recent_turns],
            {"role": "user", "content": user_text},
        ]
        res = await self.model_router.generate(task_type="conversation", messages=messages)
        return AgentResult(status=AgentStatus.SUCCESS, message=res.get("content", ""), data={"reply": res.get("content")})
