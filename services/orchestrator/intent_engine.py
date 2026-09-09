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

    async def classify_intent(self, user_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Classify user intent into target category and primary agent."""
        text_lower = user_text.lower().strip()
        text_clean = re.sub(r"^(?:hey\s+)?rio[,:\s]*", "", text_lower).strip()

        # Fast heuristic checks for ultra-low latency reflexes
        if text_clean in ("hi", "hello", "hey", "how are you?", "how are you", "who are you?", "help", "thanks", "thank you"):
            return {"category": IntentCategory.CONVERSATION, "agent_id": "conversation_agent", "is_task": False}

        if "search" in text_clean or "browse" in text_clean or "google" in text_clean:
            return {"category": IntentCategory.BROWSER_SEARCH, "agent_id": "browser_agent", "is_task": True}

        if text_clean.startswith(("open ", "launch ", "start ")) or any(k in text_clean for k in ("whatsapp", "click", "type ", "take a screenshot", "screenshot", "record my screen", "record screen")):
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
