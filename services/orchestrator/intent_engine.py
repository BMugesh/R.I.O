"""Intent and Task Understanding Engine for R.I.O.

Uses fast classification (llama-3.1-8b-instant) to determine intent, required agents,
and whether a request is conversational chit-chat vs an executable task graph.
"""

import re
from enum import Enum
from typing import Any, Dict, List, Optional
from services.model_router.router import ModelRouter


class IntentCategory(str, Enum):
    CONVERSATION = "conversation"
    DEVICE_ACTION = "device_action"
    SYSTEM_TELEMETRY = "system_telemetry"
    BROWSER_SEARCH = "browser_search"
    CODING = "coding"
    RESEARCH = "research"
    FILESYSTEM = "filesystem"
    GITHUB = "github"
    QUANTUM = "quantum"
    MEMORY_UPDATE = "memory_update"
    APPROVAL_DECISION = "approval_decision"


class IntentEngine:
    """Classifies user intent and target execution domains."""

    def __init__(self, model_router: Optional[ModelRouter] = None):
        self.model_router = model_router or ModelRouter()

    # Polite preamble patterns to strip before action verb detection.
    # Fixes "Can you open Chrome?" being classified as conversation instead of action.
    _PREAMBLE_PATTERNS = [
        re.compile(r"^(?:can|could|would|will)\s+you\s+(?:please\s+)?", re.IGNORECASE),
        re.compile(r"^(?:please|kindly)\s+", re.IGNORECASE),
        re.compile(r"^(?:i\s+want\s+you\s+to|i\s+need\s+you\s+to|i\s+would\s+like\s+you\s+to)\s+", re.IGNORECASE),
        re.compile(r"^(?:help\s+me\s+(?:to\s+)?|assist\s+me\s+(?:to\s+)?)", re.IGNORECASE),
        re.compile(r"^(?:go\s+ahead\s+and\s+|just\s+)", re.IGNORECASE),
    ]

    # Conversation-ending tokens that should result in SILENT (no response).
    _DISMISSAL_TOKENS = frozenset({
        "thanks", "thank you", "thanks a lot", "thank you so much",
        "okay", "ok", "alright", "all right",
        "got it", "gotcha", "understood",
        "cool", "great", "good", "perfect", "nice", "fine", "awesome", "wonderful",
        "that's all", "thats all", "that is all",
        "no worries", "no problem", "np", "nw",
        "sure", "yep", "yeah", "right",
        "bye", "goodbye", "good night", "goodnight", "night",
        "roger", "roger that", "copy", "copy that",
        "noted", "fair enough", "cheers",
    })

    async def classify_intent(self, user_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Classify user intent into target category and primary agent."""
        text_lower = user_text.lower().strip()
        text_clean = re.sub(r"^(?:hey\s+)?rio[,:\s]*", "", text_lower).strip()
        text_norm = text_clean.rstrip(".!?,;:")

        # ── Dismissal detection (conversation-ending tokens) → SILENT ──
        if text_norm in self._DISMISSAL_TOKENS:
            return {"category": IntentCategory.CONVERSATION, "agent_id": "conversation_agent", "is_task": False, "is_dismissal": True}

        # ── Stop command check (instant halt) ──
        if text_norm in ("stop", "halt", "cancel", "abort"):
            return {"category": IntentCategory.CONVERSATION, "agent_id": "conversation_agent", "is_task": False, "is_stop": True}

        # ── Standby command check ──
        if text_norm in ("standby", "stand by", "go to sleep", "sleep"):
            return {"category": IntentCategory.CONVERSATION, "agent_id": "conversation_agent", "is_task": False, "is_standby": True}

        # Fast heuristic checks for ultra-low latency reflexes
        greeting_tokens = ("hi", "hello", "hey", "hey rio", "hi rio", "hello rio", "rio", "how are you?", "how are you", "who are you?", "help")
        if text_norm in greeting_tokens or text_clean in greeting_tokens or (not text_norm and any(text_lower.startswith(g) for g in ("hey", "hi", "hello", "rio"))):
            return {"category": IntentCategory.CONVERSATION, "agent_id": "conversation_agent", "is_task": False, "is_greeting": True}

        # Local system telemetry check (zero cloud latency)
        if any(re.search(pat, text_clean) for pat in (
            r"\b(?:what(?:'s|\s+is)?(?:\s+the)?\s+time|current\s+time|tell\s+me\s+the\s+time|time\s+now)\b",
            r"\b(?:what(?:'s|\s+is)?(?:\s+the|\s+today's)?\s+date|what\s+day\s+is\s+(?:it|today)|today's\s+date)\b",
            r"\b(?:what(?:'s|\s+is)?(?:\s+the)?\s+timezone|what\s+timezone)\b",
            r"\b(?:what\s+gpu(?:\s+do\s+i\s+have)?|what(?:'s|\s+is)?(?:\s+my)?\s+gpu|show(?:\s+my)?\s+gpu|gpu\s+usage|gpu\s+temp(?:erature)?|how\s+much\s+vram)\b",
            r"\b(?:how\s+much\s+ram|what(?:'s|\s+is)?(?:\s+my)?\s+ram|ram\s+usage|memory\s+usage|how\s+much\s+memory|ram\s+is\s+free|free\s+ram|free\s+memory)\b",
            r"\b(?:what(?:'s|\s+is)?(?:\s+my)?\s+cpu|cpu\s+usage|cpu\s+load|how\s+many\s+cores)\b",
            r"\b(?:what(?:'s|\s+is)?(?:\s+my)?\s+battery|battery\s+(?:level|status|percentage)|is(?:\s+(?:the|my))?\s+laptop\s+plugged\s+in|laptop\s+plugged\s+in|is\s+plugged\s+in)\b",
            r"\b(?:how\s+much\s+disk|disk\s+space|free\s+space|storage\s+space)\b",
            r"\b(?:what\s+windows\s+are\s+open|list\s+open\s+windows|what\s+apps\s+are\s+open|running\s+processes|list\s+processes)\b",
            r"\b(?:what\s+os|what\s+operating\s+system|what\s+windows\s+version)\b",
            r"\b(?:is\s+[a-zA-Z0-9\-_ ]+\s+(?:running|open|active)|check\s+if\s+[a-zA-Z0-9\-_ ]+\s+is\s+(?:running|open|active))\b",
        )):
            return {"category": IntentCategory.SYSTEM_TELEMETRY, "agent_id": "local_system_agent", "is_task": True}

        if "search" in text_clean or "browse" in text_clean or "google" in text_clean:
            return {"category": IntentCategory.BROWSER_SEARCH, "agent_id": "browser_agent", "is_task": True}

        if any(k in text_clean for k in ("coding environment", "ready for coding", "setup coding", "prepare workspace", "prepare my workspace", "get my laptop ready")):
            return {"category": IntentCategory.DEVICE_ACTION, "agent_id": "computer_agent", "is_task": True}

        # ── Strip polite preambles before action verb detection ──
        # This fixes "Can you open Chrome?" → "open Chrome" → DEVICE_ACTION
        action_candidate = text_clean
        for pat in self._PREAMBLE_PATTERNS:
            action_candidate = pat.sub("", action_candidate).strip()

        if action_candidate.startswith(("open ", "launch ", "start ")) or any(k in text_clean for k in ("whatsapp", "click", "type ", "take a screenshot", "screenshot", "record my screen", "record screen")):
            return {"category": IntentCategory.DEVICE_ACTION, "agent_id": "computer_agent", "is_task": True}

        if any(k in text_clean for k in ("qaoa", "vqe", "quantum", "maxcut", "grover", "bell state")):
            return {"category": IntentCategory.QUANTUM, "agent_id": "quantum_agent", "is_task": True}

        if any(k in text_clean for k in ("github", "repo", "commit", "create issue", "pull request")):
            return {"category": IntentCategory.GITHUB, "agent_id": "github_agent", "is_task": True}

        if any(k in text_clean for k in ("remember that", "remember my", "forget that", "forget what i told you")):
            return {"category": IntentCategory.MEMORY_UPDATE, "agent_id": "memory_agent", "is_task": True}

        if any(k in text_clean for k in ("write a python", "debug this code", "create a function", "refactor", "implement class")):
            return {"category": IntentCategory.CODING, "agent_id": "coding_agent", "is_task": True}

        if any(k in text_clean for k in ("read file", "create file", "list files", "find file", "save to file")):
            return {"category": IntentCategory.FILESYSTEM, "agent_id": "filesystem_agent", "is_task": True}

        if any(k in text_clean for k in ("research", "explain in detail", "analyze document", "generate report")):
            return {"category": IntentCategory.RESEARCH, "agent_id": "research_agent", "is_task": True}

        # Model-based classification fallback via fast classification
        try:
            res = await self.model_router.generate(
                task_type="fast_classification",
                messages=[
                    {
                        "role": "system",
                        "content": "You are R.I.O. Intent Classifier. Classify the user input into one category: conversation, device_action, browser_search, coding, research, filesystem, github, quantum, memory_update. Output ONLY the category name.",
                    },
                    {"role": "user", "content": user_text},
                ],
                max_tokens=20,
            )
            cat_str = res.get("content", "").strip().lower()
            for cat in IntentCategory:
                if cat.value in cat_str:
                    return {
                        "category": cat,
                        "agent_id": f"{cat.value.replace('_action', '')}_agent",
                        "is_task": cat != IntentCategory.CONVERSATION,
                    }
        except Exception:
            pass

        return {"category": IntentCategory.CONVERSATION, "agent_id": "conversation_agent", "is_task": False}

