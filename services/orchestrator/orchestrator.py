"""Central Orchestration Facade for R.I.O. (Reasoning Intelligence Orchestration).

Coordinates the end-to-end lifecycle:
Universal Input -> Context Assembly -> Intent Classification -> Memory Retrieval ->
DAG Planning -> Model & Agent Selection -> Safety Check -> Execution ->
Observation -> Verification -> Failure Recovery -> Natural Response Synthesis.
"""

from datetime import datetime, timezone
import logging
import time
from typing import Any, Callable, Dict, List, Optional
from packages.schemas.agents import AgentRiskLevel
from packages.schemas.chat import ChatRequest, ChatResponse, DeveloperTrace
from packages.schemas.events import EventType, RIOEvent
from packages.schemas.input import InputType, RIOInput
from packages.schemas.tasks import Task, TaskPlan, TaskStatus
from services.memory.memory_manager import MemoryManager
from services.model_router.router import ModelRouter
from services.orchestrator.context_engine import ContextEngine
from services.orchestrator.dag_planner import DAGPlanner
from services.orchestrator.execution_engine import ExecutionEngine
from services.orchestrator.input_processor import InputProcessor
from services.orchestrator.intent_engine import IntentEngine
from services.orchestrator.response_engine import ResponseEngine
from services.safety.approval_engine import ApprovalEngine
from services.safety.policy_engine import PolicyEngine
from services.verification.engine import VerificationEngine

logger = logging.getLogger("rio.orchestrator")


class RIOOrchestrator:
    """Core R.I.O. Operating System Engine."""

    def __init__(
        self,
        model_router: Optional[ModelRouter] = None,
        memory_manager: Optional[MemoryManager] = None,
        policy_engine: Optional[PolicyEngine] = None,
        approval_engine: Optional[ApprovalEngine] = None,
        verification_engine: Optional[VerificationEngine] = None,
        event_callback: Optional[Callable[[RIOEvent], Any]] = None,
    ):
        self.model_router = model_router or ModelRouter()
        self.memory_manager = memory_manager or MemoryManager()
        self.policy_engine = policy_engine or PolicyEngine()
        self.approval_engine = approval_engine or ApprovalEngine()
        self.verification_engine = verification_engine or VerificationEngine()
        self.event_callback = event_callback

        self.input_processor = InputProcessor()
        self.context_engine = ContextEngine(memory_manager=self.memory_manager)
        self.intent_engine = IntentEngine(model_router=self.model_router)
        self.dag_planner = DAGPlanner(policy_engine=self.policy_engine, model_router=self.model_router)
        self.execution_engine = ExecutionEngine(
            approval_engine=self.approval_engine,
            verification_engine=self.verification_engine,
            event_callback=self.event_callback,
        )
        self.response_engine = ResponseEngine(model_router=self.model_router)

        self._active_tasks: Dict[str, Task] = {}

    def register_agent(self, agent_id: str, agent_instance: Any) -> None:
        """Register an agent in the execution engine."""
        self.execution_engine.register_agent(agent_id, agent_instance)

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        """Process incoming chat request through the full R.I.O. lifecycle."""
        start_time = time.time()
        session_id = request.session_id or "default_session"
        user_id = request.user_id or "default_user"

        # 1. Normalize Input
        rio_input = self.input_processor.process_raw(
            raw_payload=request.message,
            input_type=request.input_type,
            source="web_chat",
            metadata={"session_id": session_id, "user_id": user_id, "device_id": request.device_id},
        )

        # 2. Context Engine Assembly & Short-term recall
        context = await self.context_engine.build_context(rio_input, active_device_id=request.device_id)

        # 3. Intent & Task Understanding
        intent_info = await self.intent_engine.classify_intent(request.message, context)

        task_obj: Optional[Task] = None
        reply_text = ""

        # 4. Handle Execution / Task Planning
        if intent_info.get("is_task", False):
            # Generate DAG Plan
            plan = await self.dag_planner.create_plan(goal=request.message, context=context)
            task_obj = Task(
                session_id=session_id,
                user_id=user_id,
                goal=request.message,
                plan=plan,
                status=TaskStatus.PLANNING,
            )
            self._active_tasks[task_obj.id] = task_obj

            # Execute Task Graph
            task_obj = await self.execution_engine.execute_task(task_obj, context=context)

            # Synthesize verified natural response
            reply_text = await self.response_engine.generate_response(
                user_message=request.message,
                task=task_obj,
                context=context,
                developer_mode=request.developer_mode,
            )
        else:
            # Conversational path
            reply_text = await self.response_engine.generate_response(
                user_message=request.message,
                task=None,
                context=context,
                developer_mode=request.developer_mode,
            )

        # 5. Record conversational turns in memory
        await self.memory_manager.add_conversation_turn(session_id=session_id, role="user", content=request.message)
        await self.memory_manager.add_conversation_turn(session_id=session_id, role="assistant", content=reply_text)

        # 6. Build optional developer trace if requested
        dev_trace = None
        if request.developer_mode:
            latency = (time.time() - start_time) * 1000
            dev_trace = DeveloperTrace(
                task_id=task_obj.id if task_obj else None,
                agent_id=intent_info.get("agent_id"),
                model_id=self.model_router.resolve_model(intent_info.get("category", "conversation")),
                plan=task_obj.plan if task_obj else None,
                steps=task_obj.plan.steps if task_obj and task_obj.plan else [],
                latency_ms=latency,
            )

        return ChatResponse(
            session_id=session_id,
            reply=reply_text,
            task_id=task_obj.id if task_obj else None,
            status=task_obj.status.value if task_obj else "completed",
            developer_trace=dev_trace,
        )

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._active_tasks.get(task_id)
