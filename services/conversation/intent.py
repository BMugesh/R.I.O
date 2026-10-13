"""Intent Classification & Follow-Up Understanding for R.I.O. (Milestone 5.x).

Distinguishes:
- System commands (standby, shutdown, stop)
- Conversational questions (e.g. "What is RAG?")
- Laptop actions (e.g. "Open Chrome", "Run the tests")
- Mixed requests (e.g. "Open Chrome and explain how browser automation works")
and resolves contextual follow-ups ("open it", "run the tests", "which one").
"""

from enum import Enum
import logging
import re
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, Field

from services.conversation.context import ConversationContext

logger = logging.getLogger("rio.conversation.intent")


class IntentType(str, Enum):
    SYSTEM_STANDBY = "system_standby"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SYSTEM_STOP = "system_stop"
    CONVERSATIONAL = "conversational"
    ACTION = "action"
    MIXED = "mixed"


class ActionRequestContract(BaseModel):
    """Structured contract emitted when Groq / IntentClassifier detects an action request."""
    type: str = "action_request"
    goal: str
    requires_execution: bool = True
    risk: str = "low"
    target: str = "local_laptop"
    action_type: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class IntentClassifier:
    """Classifies user intent and rewrites contextual references."""

    ACTION_VERBS = [
        "open", "launch", "start", "run", "execute", "play", "pause",
        "close", "terminate", "kill", "search", "navigate", "click",
        "type", "screenshot", "create", "delete", "remove", "write",
        "build", "test", "install", "open up", "take", "format",
        "capture", "show", "display", "download", "find", "send",
        "minimize", "maximize", "focus", "switch to", "switch", "restore", "check",
    ]

    CONVERSATIONAL_STARTERS = [
        "what", "why", "how", "who", "when", "where", "explain",
        "tell me", "can you explain", "difference between",
        "which one", "do you know", "recommend",
    ]

    @classmethod
    def resolve_follow_ups(cls, text: str, context: Optional[ConversationContext]) -> str:
        """Resolve contextual pronouns ('it', 'that', 'the tests') using active context."""
        if not context or not text:
            return text

        resolved = text.strip()
        lower = resolved.lower()

        # Resolve 'it' / 'that'
        last_target = context.get_entity("it") or context.last_action_target
        if last_target:
            # e.g. "open it" -> "open <target>"
            resolved = re.sub(
                r"\b(open|launch|start|close|minimize|maximize|focus|show|switch to)\s+(it|that)\b",
                rf"\1 {last_target}",
                resolved,
                flags=re.IGNORECASE,
            )

        # Resolve 'the project'
        last_project = context.get_entity("project")
        if last_project:
            resolved = re.sub(r"\b(open|build|test)\s+(my\s+project|the\s+project)\b", rf"\1 {last_project}", resolved, flags=re.IGNORECASE)

        return resolved

    @classmethod
    def extract_action_goal(cls, text: str) -> Optional[str]:
        """Strip conversational/polite preambles and identify action goals."""
        clean = text.strip()
        candidate = clean

        if re.search(r"^(?:can|could|would|will)\s+you\s+(?:please\s+)?(?:open|run|launch|get|find|show|close|minimize|maximize|focus|switch)\b", candidate, flags=re.IGNORECASE):
            candidate = re.sub(
                r"^(?:can|could|would|will)\s+you\s+(?:please\s+)?(open|run|launch|get|find|show|close|minimize|maximize|focus|switch)\s*(?:me|to)?\b",
                r"\1",
                candidate,
                flags=re.IGNORECASE,
            ).strip()
        else:
            for pat in [
                r"^(?:can|could|would|will)\s+you\s+(?:please\s+)?",
                r"^(?:please|kindly)\s+",
                r"^(?:i\s+want\s+you\s+to|i\s+need\s+you\s+to|i\s+would\s+like\s+you\s+to)\s+",
                r"^(?:help\s+me\s+(?:to\s+)?|assist\s+me\s+(?:to\s+)?)\b",
            ]:
                if re.search(pat, candidate, flags=re.IGNORECASE):
                    candidate = re.sub(pat, "", candidate, flags=re.IGNORECASE).strip()
                    break

        candidate_lower = candidate.lower().rstrip(".,!?")
        starts_with_action = any(
            candidate_lower.startswith(v + " ") or candidate_lower == v
            for v in cls.ACTION_VERBS
        )
        is_conv_starter = any(
            candidate_lower.startswith(q + " ") or candidate_lower == q
            for q in cls.CONVERSATIONAL_STARTERS
        )

        if starts_with_action and not is_conv_starter:
            return candidate.rstrip(".,!?")
        return None

    @classmethod
    def classify(cls, text: str, context: Optional[ConversationContext] = None) -> Tuple[IntentType, Optional[ActionRequestContract]]:
        """Classify user utterance into IntentType and optional ActionRequestContract."""
        clean = text.strip()
        lower = clean.lower()
        cmd_norm = lower.rstrip(".!?").strip()

        # 1. System Commands
        if cmd_norm in ("rio, standby", "rio standby", "standby", "stand by", "rio, stand by", "rio stand by", "go to sleep", "sleep"):
            return IntentType.SYSTEM_STANDBY, None

        if cmd_norm in ("rio, shut down", "rio shut down", "shut down", "shutdown", "exit", "turn off"):
            return IntentType.SYSTEM_SHUTDOWN, None

        if cmd_norm in ("rio, stop", "rio stop", "stop", "cancel", "halt"):
            return IntentType.SYSTEM_STOP, None

        # 2. Application Status Query: "is <app> running?", "is <app> open?", "check if <app> is running"
        status_match = re.match(r"^(?:is\s+([a-zA-Z0-9\-_ ]+?)\s+(?:running|open|active)|check if\s+([a-zA-Z0-9\-_ ]+?)\s+is\s+(?:running|open|active))\??$", lower)
        if status_match:
            app_name = (status_match.group(1) or status_match.group(2)).strip()
            if app_name in ("it", "that") and context:
                app_name = context.get_entity("it") or context.last_action_target or app_name
            contract = ActionRequestContract(
                goal=f"status of {app_name}",
                requires_execution=True,
                risk="low",
                target="local_laptop",
                action_type="application.status",
                parameters={"app_name": app_name},
            )
            return IntentType.ACTION, contract

        # 3. Local System Telemetry Queries (Time, Date, GPU, RAM, CPU, Battery, Windows, OS)
        system_telemetry_patterns = [
            r"\b(?:what(?:'s|\s+is)?(?:\s+the)?\s+time|current\s+time|tell\s+me\s+the\s+time|time\s+now)\b",
            r"\b(?:what(?:'s|\s+is)?(?:\s+the|\s+today's)?\s+date|what\s+day\s+is\s+(?:it|today)|today's\s+date)\b",
            r"\b(?:what(?:'s|\s+is)?(?:\s+the)?\s+timezone|what\s+timezone)\b",
            r"\b(?:what\s+gpu(?:\s+do\s+i\s+have)?|what(?:'s|\s+is)?(?:\s+my)?\s+gpu|show(?:\s+my)?\s+gpu|gpu\s+usage|gpu\s+temp(?:erature)?|how\s+much\s+vram)\b",
            r"\b(?:how\s+much\s+ram|what(?:'s|\s+is)?(?:\s+my)?\s+ram|ram\s+usage|memory\s+usage|how\s+much\s+memory)\b",
            r"\b(?:what(?:'s|\s+is)?(?:\s+my)?\s+cpu|cpu\s+usage|cpu\s+load|how\s+many\s+cores)\b",
            r"\b(?:what(?:'s|\s+is)?(?:\s+my)?\s+battery|battery\s+(?:level|status|percentage)|is(?:\s+(?:the|my))?\s+laptop\s+plugged\s+in|laptop\s+plugged\s+in|is\s+plugged\s+in)\b",
            r"\b(?:how\s+much\s+disk|disk\s+space|free\s+space|storage\s+space)\b",
            r"\b(?:what\s+windows\s+are\s+open|list\s+open\s+windows|what\s+apps\s+are\s+open)\b",
            r"\b(?:what\s+os|what\s+operating\s+system|what\s+windows\s+version)\b",
        ]
        if any(re.search(pat, lower) for pat in system_telemetry_patterns):
            contract = ActionRequestContract(
                goal=clean,
                requires_execution=True,
                risk="low",
                target="local_system",
                action_type="system.telemetry",
                parameters={"query": clean},
            )
            return IntentType.ACTION, contract

        # 3. Mixed: contains both an action verb AND an explanation conjunction
        has_action_verb = any(lower.startswith(v + " ") or f" {v} " in lower for v in cls.ACTION_VERBS)
        has_question_term = any(q in lower for q in ("explain", "what is", "how does", "tell me how"))

        if has_action_verb and has_question_term and (" and " in lower or " then " in lower):
            resolved = cls.resolve_follow_ups(clean, context)
            contract = ActionRequestContract(
                goal=resolved,
                requires_execution=True,
                risk="low",
                target="local_laptop",
            )
            return IntentType.MIXED, contract

        # 4. Action Request (Direct or Natural Polite Request)
        action_goal = cls.extract_action_goal(clean)
        if action_goal:
            resolved = cls.resolve_follow_ups(action_goal, context)
            resolved_lower = resolved.lower()
            risk = "high" if any(w in resolved_lower for w in ("delete", "remove", "kill", "format", "drop")) else "low"
            contract = ActionRequestContract(
                goal=resolved,
                requires_execution=True,
                risk=risk,
                target="local_laptop",
            )
            return IntentType.ACTION, contract

        # 5. Conversational / Q&A
        return IntentType.CONVERSATIONAL, None
