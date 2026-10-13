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
from services.device_router.router import DeviceRouter
from services.memory.memory_manager import MemoryManager
from services.model_router.router import ModelRouter
from services.orchestrator.context_engine import ContextEngine
from services.orchestrator.dag_planner import DAGPlanner
from services.planning.planner import IntelligentPlanner
from services.orchestrator.execution_engine import ExecutionEngine
from services.orchestrator.input_processor import InputProcessor
from services.orchestrator.intent_engine import IntentEngine
from services.orchestrator.response_engine import ResponseEngine
from services.orchestrator.speech_gate import SpeechDecision, SpeechGate
from services.safety.approval_engine import ApprovalEngine
from services.safety.policy_engine import PolicyEngine
from services.scheduler.scheduler import ScheduledTaskState, TaskScheduler
from services.verification.engine import VerificationEngine
from packages.schemas.devices import OriginContext
from services.compute.router import ComputeRouter, get_compute_router
from services.profiler.spans import SpanType
from services.profiler.tracer import ProfileTracer, get_tracer

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
        device_router: Optional[DeviceRouter] = None,
        scheduler: Optional[TaskScheduler] = None,
        compute_router: Optional[ComputeRouter] = None,
        event_callback: Optional[Callable[[RIOEvent], Any]] = None,
    ):
        self.model_router = model_router or ModelRouter()
        self.memory_manager = memory_manager or MemoryManager()
        self.policy_engine = policy_engine or PolicyEngine()
        self.approval_engine = approval_engine or ApprovalEngine()
        self.verification_engine = verification_engine or VerificationEngine()
        self.device_router = device_router or DeviceRouter()
        self.scheduler = scheduler or TaskScheduler()
        self.compute_router = compute_router or get_compute_router()
        self.tracer = get_tracer()
        self.event_callback = event_callback

        self.input_processor = InputProcessor()
        self.context_engine = ContextEngine(memory_manager=self.memory_manager)
        self.intent_engine = IntentEngine(model_router=self.model_router)
        self.dag_planner = DAGPlanner(
            policy_engine=self.policy_engine,
            model_router=self.model_router,
            device_router=self.device_router,
        )
        self.intelligent_planner = IntelligentPlanner(dag_planner_fallback=self.dag_planner)
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

        # 1. Assemble Origin Context & Normalize Input
        trace = self.tracer.start_trace(task_id=session_id, goal=request.message)
        origin_ctx = request.origin_context
        if not origin_ctx:
            orig_dev = request.origin_device_id or request.device_id
            itype = request.interface_type or ("cli" if "cli" in session_id.lower() else "web")
            origin_ctx = OriginContext(
                session_id=session_id,
                interface_type=itype,
                origin_device_id=orig_dev,
            )

        with self.tracer.span("input_processing", SpanType.INPUT):
            rio_input = self.input_processor.process_raw(
                raw_payload=request.message,
                input_type=request.input_type,
                source=str(origin_ctx.interface_type.value if hasattr(origin_ctx.interface_type, "value") else origin_ctx.interface_type),
                metadata={
                    "session_id": session_id,
                    "user_id": user_id,
                    "device_id": origin_ctx.origin_device_id,
                    "interface_type": str(origin_ctx.interface_type.value if hasattr(origin_ctx.interface_type, "value") else origin_ctx.interface_type),
                    "origin_context": origin_ctx,
                },
            )

        # 2. Context Engine Assembly & Short-term recall
        with self.tracer.span("context_assembly", SpanType.INPUT):
            context = await self.context_engine.build_context(rio_input, active_device_id=request.device_id)

        # 3. Intent & Task Understanding
        with self.tracer.span("intent_detection", SpanType.INTENT):
            intent_info = await self.intent_engine.classify_intent(request.message, context)

        # ── FRIDAY MODE: Speech Decision Gate ──
        # Evaluate whether R.I.O. should speak BEFORE generating any response.
        # This prevents Groq calls for dismissals ("thanks", "okay", "good", etc.)
        speech_decision = SpeechGate.evaluate(
            user_message=request.message,
            intent_info=intent_info,
        )

        # If the user sent a dismissal (conversation-ending token), return immediately.
        # Zero Groq calls. Zero TTS. Zero filler.
        if speech_decision == SpeechDecision.SILENT:
            completed_trace = self.tracer.end_trace(task_id=session_id)
            return ChatResponse(
                session_id=session_id,
                reply="",
                task_id=None,
                status="completed",
                developer_trace=None,
            )

        # ── Handle instant Stop/Halt ──
        if intent_info.get("is_stop", False):
            for tid in list(self._active_tasks.keys()):
                self.execution_engine.cancel_task(tid)
            reply_text = "Stopped."
            await self.memory_manager.add_conversation_turn(session_id=session_id, role="user", content=request.message)
            await self.memory_manager.add_conversation_turn(session_id=session_id, role="assistant", content=reply_text)
            self.tracer.end_trace(task_id=session_id)
            return ChatResponse(
                session_id=session_id,
                reply=reply_text,
                task_id=None,
                status="completed",
                developer_trace=None,
            )

        # ── Handle Standby ──
        if intent_info.get("is_standby", False):
            reply_text = "Standing by."
            await self.memory_manager.add_conversation_turn(session_id=session_id, role="user", content=request.message)
            await self.memory_manager.add_conversation_turn(session_id=session_id, role="assistant", content=reply_text)
            self.tracer.end_trace(task_id=session_id)
            return ChatResponse(
                session_id=session_id,
                reply=reply_text,
                task_id=None,
                status="completed",
                developer_trace=None,
            )

        task_obj: Optional[Task] = None
        reply_text = ""

        # 4. Handle Execution / Task Planning
        if intent_info.get("is_task", False):
            import re
            m_sched = re.search(r"\bat\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d{1,2}\s*(?:am|pm))\b|\bin\s+(\d+\s*(?:minutes?|hours?))\b", request.message, re.IGNORECASE)
            
            # Generate DAG Plan
            with self.tracer.span("dag_planning", SpanType.PLANNING):
                plan = await self.intelligent_planner.plan(goal=request.message, context=context)
            task_obj = Task(
                session_id=session_id,
                user_id=user_id,
                goal=request.message,
                plan=plan,
                status=TaskStatus.PLANNING,
            )
            self._active_tasks[task_obj.id] = task_obj

            if m_sched:
                time_str = m_sched.group(0).strip()
                dev_res = (context or {}).get("device_resolution")
                orig_id = (dev_res.origin_device_id if dev_res else None) or origin_ctx.origin_device_id or "phone-01"
                exec_id = (dev_res.execution_device_id if dev_res else None) or orig_id
                
                sched_task = self.scheduler.schedule(
                    goal=request.message,
                    trigger_time_iso=time_str,
                    origin_device_id=orig_id,
                    execution_device_id=exec_id,
                    plan=plan,
                    metadata={"session_id": session_id, "user_id": user_id},
                )
                task_obj.metadata["scheduled_task_id"] = sched_task.id
                task_obj.metadata["scheduled_time"] = time_str
                task_obj.status = TaskStatus.PENDING
                
                device_label = "your phone" if "phone" in exec_id or "android" in exec_id else ("your laptop" if "laptop" in exec_id or "desktop" in exec_id else f"device {exec_id}")
                reply_text = f"Scheduled: '{request.message}' {time_str} on {device_label}."
            else:
                # Execute Task Graph immediately
                task_obj = await self.execution_engine.execute_task(task_obj, context=context)

                # Re-evaluate speech decision after task execution
                task_speech = SpeechGate.evaluate(
                    user_message=request.message,
                    intent_info=intent_info,
                    task_status=task_obj.status.value if task_obj else None,
                )

                # Synthesize verified natural response
                with self.tracer.span("response_synthesis", SpanType.RESPONSE):
                    reply_text = await self.response_engine.generate_response(
                        user_message=request.message,
                        task=task_obj,
                        context=context,
                        developer_mode=request.developer_mode,
                        speech_decision=task_speech,
                    )
        else:
            # Conversational path — greetings get a brief "Yes?" response
            if intent_info.get("is_greeting", False):
                reply_text = "Yes?"
            else:
                with self.tracer.span("response_synthesis", SpanType.RESPONSE):
                    reply_text = await self.response_engine.generate_response(
                        user_message=request.message,
                        task=None,
                        context=context,
                        developer_mode=request.developer_mode,
                        speech_decision=speech_decision,
                    )

        # 5. Record conversational turns in memory (skip for empty/silent responses)
        await self.memory_manager.add_conversation_turn(session_id=session_id, role="user", content=request.message)
        if reply_text:
            await self.memory_manager.add_conversation_turn(session_id=session_id, role="assistant", content=reply_text)

        # Finish Profiler Trace
        completed_trace = self.tracer.end_trace(task_id=session_id)

        # 6. Build optional developer trace if requested
        dev_trace = None
        if request.developer_mode:
            latency = (time.time() - start_time) * 1000
            dev_resolution = (context or {}).get("device_resolution")
            orig_id = (dev_resolution.origin_device_id if dev_resolution else None) or origin_ctx.origin_device_id
            exec_id = (dev_resolution.execution_device_id if dev_resolution else None)
            res_reason = (dev_resolution.reason if dev_resolution else None) or "default"
            exp_override = (dev_resolution.explicit_override if dev_resolution else False)

            dev_trace = DeveloperTrace(
                task_id=task_obj.id if task_obj else None,
                agent_id=intent_info.get("agent_id"),
                model_id=self.model_router.resolve_model(intent_info.get("category", "conversation")),
                origin_device_id=orig_id,
                execution_device_id=exec_id,
                resolution_reason=res_reason,
                explicit_override=exp_override,
                plan=task_obj.plan if task_obj else None,
                steps=task_obj.plan.steps if task_obj and task_obj.plan else [],
                compute_trace=completed_trace.to_dict() if completed_trace else None,
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

