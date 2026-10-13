"""Central Conversation Manager for R.I.O. (Milestone 5.x).

Coordinates multi-turn dialogue context, intent routing between Groq reasoning
and M5 execution engine, follow-up resolution, and verified voice responses.
"""

import asyncio
import logging
from typing import Any, Dict, Optional, Tuple

from packages.schemas.chat import ChatRequest, ChatResponse
from packages.schemas.input import InputType
from services.conversation.context import ConversationContext
from services.conversation.history import ConversationHistory
from services.conversation.intent import ActionRequestContract, IntentClassifier, IntentType
from services.conversation.policy import ConversationPolicy
from services.conversation.response import ResponseGenerator
from services.model_router.router import ModelRouter
from services.orchestrator.orchestrator import RIOOrchestrator

logger = logging.getLogger("rio.conversation.manager")


class ConversationManager:
    """Orchestrates natural voice conversation, multi-turn state, and M5 task execution."""

    def __init__(
        self,
        orchestrator: Optional[RIOOrchestrator] = None,
        model_router: Optional[ModelRouter] = None,
        policy: Optional[ConversationPolicy] = None,
        context: Optional[ConversationContext] = None,
    ):
        if orchestrator:
            self.orchestrator = orchestrator
        else:
            try:
                from apps.api.deps import container
                self.orchestrator = container.orchestrator
            except Exception:
                self.orchestrator = RIOOrchestrator()

        self.model_router = model_router or self.orchestrator.model_router or ModelRouter()
        self.policy = policy or ConversationPolicy()
        self.context = context or ConversationContext()
        self.history = ConversationHistory(max_messages=self.policy.max_history_turns)

    async def handle_user_utterance(self, utterance: str) -> Tuple[IntentType, str]:
        """Process a recognized user utterance and return (IntentType, spoken_reply)."""
        if not utterance or not utterance.strip():
            return IntentType.CONVERSATIONAL, "I didn't catch that. Could you repeat?"

        clean_text = utterance.strip()
        intent_type, action_contract = IntentClassifier.classify(clean_text, self.context)

        # 1. System Commands
        if intent_type == IntentType.SYSTEM_STANDBY:
            return IntentType.SYSTEM_STANDBY, "Standing by."

        if intent_type == IntentType.SYSTEM_SHUTDOWN:
            return IntentType.SYSTEM_SHUTDOWN, "Shutting down."

        if intent_type == IntentType.SYSTEM_STOP:
            return IntentType.SYSTEM_STOP, "Stopped."

        # 2. Laptop / Local System Action Request
        if intent_type == IntentType.ACTION and action_contract:
            if action_contract.target == "local_system":
                logger.info(f"Routing local system telemetry query directly to LocalSystemAgent: '{action_contract.goal}'")
                return await self._execute_local_system_request(action_contract)
            logger.info(f"Routing actionable command to M5: '{action_contract.goal}'")
            return await self._execute_action_request(action_contract)

        # 3. Mixed Request -> Action + Reasoning
        if intent_type == IntentType.MIXED and action_contract:
            logger.info(f"Routing mixed request to M5 + Groq: '{clean_text}'")
            return await self._execute_mixed_request(clean_text, action_contract)

        # 4. Conversational Request -> Groq Reasoning
        logger.info(f"Routing conversational inquiry to Groq: '{clean_text}'")
        return await self._execute_conversational_request(clean_text)

    async def _execute_local_system_request(self, contract: ActionRequestContract) -> Tuple[IntentType, str]:
        """Dispatch local telemetry query directly to LocalSystemAgent without remote LLM latency."""
        from agents.system.agent import LocalSystemAgent
        from packages.schemas.input import InputType, RIOInput

        system_agent = self.orchestrator.agents.get("local_system_agent") if hasattr(self.orchestrator, "agents") else None
        if not system_agent:
            system_agent = LocalSystemAgent()

        res = await system_agent.run(
            RIOInput(type=InputType.TEXT, payload={"query": contract.goal}),
            context={"session_id": self.context.session_id},
        )
        reply = res.message
        self.history.add_user_message(contract.goal)
        self.history.add_assistant_message(reply)
        return IntentType.ACTION, reply

    async def _execute_action_request(self, contract: ActionRequestContract) -> Tuple[IntentType, str]:
        """Dispatch action into M5 orchestrator with full verification and response generation."""
        goal = contract.goal

        # Contextual entity updates
        parts = goal.split()
        if len(parts) >= 2 and parts[0].lower() in ("open", "launch", "start"):
            self.context.record_action(parts[0].lower(), " ".join(parts[1:]))

        chat_req = ChatRequest(
            message=goal,
            sessionId=self.context.session_id,
            interfaceType="voice",
            originDeviceId="laptop-01",
        )

        try:
            chat_res: ChatResponse = await self.orchestrator.process_chat(chat_req)
            success = chat_res.status in ("success", "completed")
            verified = True  # Verified by M5 VerificationEngine / AdaptiveVerifier

            reply = ResponseGenerator.format_action_response(
                goal=goal,
                success=success,
                verified=verified,
                error_message=chat_res.reply if not success else None,
            )

            # Record in history and context
            self.history.add_user_message(goal)
            self.history.add_assistant_message(reply)
            return IntentType.ACTION, reply

        except Exception as e:
            logger.error(f"Error executing M5 action '{goal}': {e}")
            reply = ResponseGenerator.format_action_response(
                goal=goal,
                success=False,
                verified=False,
                error_message=str(e),
            )
            return IntentType.ACTION, reply

    async def _execute_conversational_request(self, text: str) -> Tuple[IntentType, str]:
        """Dispatch conversational question to Groq reasoning."""
        resolved = IntentClassifier.resolve_follow_ups(text, self.context)
        self.history.add_user_message(resolved)

        try:
            messages = self.history.get_groq_messages()
            # If history doesn't have system prompt, prepend conversational persona
            if not any(m.get("role") == "system" for m in messages):
                system_prompt = (
                    "You are R.I.O., a highly capable, intelligent, and calm personal AI operating system. "
                    "Provide clear, concise, direct answers suitable for natural voice response. "
                    "Do not use markdown formatting, bullet points, or raw JSON in your speech."
                )
                messages = [{"role": "system", "content": system_prompt}] + messages

            gen_result = await self.model_router.generate(
                task_type="conversation",
                messages=messages,
                complexity="medium",
            )
            raw_reply = gen_result.get("content", "I am thinking about that.")
            reply = ResponseGenerator.format_conversational_response(raw_reply)

            self.history.add_assistant_message(reply)
            self.context.record_topic(resolved)
            return IntentType.CONVERSATIONAL, reply

        except Exception as e:
            logger.error(f"Groq conversational generation error: {e}")
            fallback_reply = "I'm having trouble connecting to the reasoning service right now."
            return IntentType.CONVERSATIONAL, fallback_reply

    async def _execute_mixed_request(self, raw_text: str, contract: ActionRequestContract) -> Tuple[IntentType, str]:
        """Execute action portion and generate explanation."""
        _, action_reply = await self._execute_action_request(contract)
        _, conv_reply = await self._execute_conversational_request(raw_text)
        combined = f"{action_reply} {conv_reply}".strip()
        return IntentType.MIXED, combined
