"""Speech Decision Gate for R.I.O. TRUE FRIDAY MODE.

Evaluates WHETHER R.I.O. should speak before any response is generated.
This is the architectural core of the silence-first runtime model:

    R.I.O. MUST REMAIN SILENT UNLESS IT HAS A REASON TO SPEAK.

SpeechGate.evaluate() runs BEFORE ResponseEngine.generate_response() and
returns a SpeechDecision that the orchestrator uses to decide whether to
generate a response, skip LLM calls, or emit a brief acknowledgement.
"""

import logging
import re
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger("rio.orchestrator.speech_gate")


class SpeechDecision(str, Enum):
    """What should R.I.O. do with its voice/text output?"""
    SILENT = "silent"                           # No response needed — be quiet
    ACKNOWLEDGE = "acknowledge"                 # Brief acknowledgement ("Yes?", "Done.")
    RESPOND = "respond"                         # Full answer to a question
    PROGRESS_UPDATE = "progress_update"         # Background task status update
    NOTIFY = "notify"                           # Background event notification
    ASK = "ask"                                 # Clarification needed from user
    ERROR = "error"                             # Report failure
    CONFIRMATION_REQUIRED = "confirmation_required"  # High-risk action needs approval


# Conversation-ending phrases that signal the user is done talking.
# When the user says any of these, R.I.O. should remain SILENT.
DISMISSAL_TOKENS = frozenset({
    "thanks", "thank you", "thanks a lot", "thank you so much",
    "okay", "ok", "alright", "all right",
    "got it", "gotcha", "understood",
    "cool", "great", "good", "perfect", "nice", "fine", "awesome", "wonderful",
    "that's all", "thats all", "that is all",
    "no worries", "no problem", "np", "nw",
    "sure", "yep", "yeah", "yes", "right",
    "bye", "goodbye", "good night", "goodnight", "night",
    "roger", "roger that", "copy", "copy that",
    "noted", "fair enough",
    "you're welcome",  # If user says this, definitely don't reply again
    "cheers",
})

# Patterns that are clearly conversation-ending even with extra words
DISMISSAL_PATTERNS = [
    r"^(?:ok(?:ay)?|alright|great|good|perfect|nice|cool|fine|awesome)\s*[.!,]*\s*(?:thanks|thank you|cheers)?[.!]*$",
    r"^(?:thanks|thank you|cheers)(?:\s+(?:rio|a lot|so much|very much|mate|buddy|dude))?[.!]*$",
    r"^(?:that'?s?\s+(?:all|it|enough|perfect|great))[.!]*$",
    r"^(?:no(?:thing)?\s+(?:else|more))[.!]*$",
    r"^(?:i'?m?\s+(?:good|fine|done|all set|sorted))(?:\s*,\s*(?:thanks|thank you|cheers))?[.!]*$",
    r"^(?:all\s+(?:good|done|set))(?:\s*,\s*(?:thanks|thank you|cheers))?[.!]*$",
    r"^(?:never\s*mind|nvm)[.!]*$",
]

# Compile patterns once
_DISMISSAL_RE = [re.compile(p, re.IGNORECASE) for p in DISMISSAL_PATTERNS]


class SpeechGate:
    """Evaluates whether R.I.O. should speak.

    This gate runs BEFORE any LLM call or response generation.
    When it returns SILENT, no Groq call is made, no TTS is triggered,
    and no response bubble is rendered.
    """

    @staticmethod
    def evaluate(
        user_message: str,
        intent_info: Optional[Dict[str, Any]] = None,
        task_status: Optional[str] = None,
        is_background_event: bool = False,
        has_question: bool = False,
    ) -> SpeechDecision:
        """Determine the appropriate speech decision for the current interaction.

        Args:
            user_message: The raw user input text.
            intent_info: Intent classification result from IntentEngine.
            task_status: Status of an executed task ("completed", "failed", etc.).
            is_background_event: Whether this was triggered by a background event.
            has_question: Whether the message contains a question.

        Returns:
            SpeechDecision indicating what R.I.O. should do.
        """
        if not user_message or not user_message.strip():
            return SpeechDecision.SILENT

        text = user_message.strip()
        text_lower = text.lower()
        text_clean = re.sub(r"^(?:hey\s+)?rio[,:\s]*", "", text_lower).strip()
        text_norm = text_clean.rstrip(".!?,;:")

        intent = intent_info or {}
        is_dismissal = intent.get("is_dismissal", False)

        # ── Rule 1: Explicit dismissal tokens → SILENT ──
        if is_dismissal or text_norm in DISMISSAL_TOKENS:
            logger.debug("SpeechGate: SILENT (dismissal token: '%s')", text_norm)
            return SpeechDecision.SILENT

        # Check dismissal patterns
        if any(p.match(text_clean) for p in _DISMISSAL_RE):
            logger.debug("SpeechGate: SILENT (dismissal pattern: '%s')", text_clean)
            return SpeechDecision.SILENT

        # ── Rule 2: Background event notifications ──
        if is_background_event:
            return SpeechDecision.NOTIFY

        # ── Rule 3: Task completed → concise ACKNOWLEDGE ──
        if task_status == "completed":
            return SpeechDecision.ACKNOWLEDGE

        # ── Rule 4: Task failed → ERROR report ──
        if task_status == "failed":
            return SpeechDecision.ERROR

        # ── Rule 5: System commands (standby/stop/shutdown) → ACKNOWLEDGE ──
        if any(sc in text_norm for sc in ("standby", "stand by", "shut down", "shutdown")):
            return SpeechDecision.ACKNOWLEDGE

        if text_norm in ("stop", "cancel", "halt", "rio stop", "rio, stop"):
            return SpeechDecision.ACKNOWLEDGE

        # ── Rule 6: Action commands → ACKNOWLEDGE (brief "Done." after execution) ──
        is_task = intent.get("is_task", False)
        if is_task:
            return SpeechDecision.ACKNOWLEDGE

        # ── Rule 7: Questions → RESPOND (full answer) ──
        if has_question or _is_question(text_clean):
            return SpeechDecision.RESPOND

        # ── Rule 8: Greetings → ACKNOWLEDGE ("Yes?") ──
        raw_norm = text_lower.rstrip(".!?,;:")
        if (
            raw_norm in ("hi", "hello", "hey", "hey rio", "hi rio", "hello rio", "rio")
            or text_norm in ("hi", "hello", "hey", "hey rio", "hi rio", "hello rio", "rio")
            or (not text_clean and any(text_lower.startswith(g) for g in ("hey", "hi", "hello", "rio")))
            or intent.get("is_greeting", False)
        ):
            return SpeechDecision.ACKNOWLEDGE

        # ── Rule 9: General conversation → RESPOND ──
        if not is_task:
            return SpeechDecision.RESPOND

        # Fallback: respond rather than be unhelpful
        return SpeechDecision.RESPOND


def _is_question(text: str) -> bool:
    """Detect if text is a question."""
    if text.rstrip().endswith("?"):
        return True
    question_starters = (
        "what", "why", "how", "who", "when", "where", "which",
        "explain", "tell me", "can you explain", "describe",
        "do you know", "is there", "are there", "does", "did",
        "will", "would", "could", "should", "shall",
    )
    lower = text.lower().strip()
    return any(lower.startswith(q + " ") or lower == q for q in question_starters)
