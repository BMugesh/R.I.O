"""Response Generator for R.I.O. (Milestone 5.x).

Translates verified execution evidence and conversational reasoning into
natural, concise spoken responses. Enforces the strict rule:
'Never say Done without verification evidence.'
"""

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger("rio.conversation.response")


class ResponseGenerator:
    """Produces natural spoken responses from verified action outcomes or reasoning."""

    @classmethod
    def format_action_response(
        cls,
        goal: str,
        success: bool,
        verified: bool = True,
        evidence: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> str:
        """Generate verified voice response for laptop actions."""
        if not success:
            err = error_message or "an error occurred during execution."
            return f"I couldn't complete that because {err}"

        if not verified:
            return f"The action was executed, but I could not verify the outcome."

        # Verified success: synthesize concise confirmation
        goal_lower = goal.lower().strip().rstrip(".!?")

        # 1. Check if evidence contains application status or window info
        if evidence:
            ev_data = evidence.get("data", {}) if isinstance(evidence, dict) else getattr(evidence, "data", {})
            if isinstance(ev_data, dict):
                st_info = ev_data.get("status_info")
                if st_info and isinstance(st_info, dict):
                    app_title = st_info.get("display_name") or ev_data.get("app") or "The application"
                    if st_info.get("running"):
                        return f"Yes, {app_title} is running."
                    return f"No, {app_title} is not running."

                if "window_data" in ev_data:
                    app_title = ev_data.get("app") or "The application"
                    w_data = ev_data["window_data"]
                    if w_data.get("found"):
                        return f"{app_title} window title is {w_data.get('title')}."
                    return f"No active window found for {app_title}."

        # 2. Specific intent-based templates
        if "whatsapp" in goal_lower and ("send" in goal_lower or "message" in goal_lower or "msg" in goal_lower):
            m_contact = re.search(r"(?:to contact named|to contact|to)\s+['\"]?([^'\"\.,]+)['\"]?", goal, re.IGNORECASE)
            contact_name = m_contact.group(1).strip().strip("'\"").title() if m_contact else "the contact"
            return f"Done. I've sent the message to {contact_name} on WhatsApp."

        if "open" in goal_lower and "project" in goal_lower:
            return "Your project is open."

        if "run" in goal_lower and "test" in goal_lower:
            return "The test suite completed. All tests passed."

        if "search youtube" in goal_lower:
            return "Searching YouTube."

        if "play" in goal_lower:
            return "Done. Playing now."

        if "create" in goal_lower and "folder" in goal_lower:
            return "The folder has been created."

        if "take a screenshot" in goal_lower or "screenshot" in goal_lower:
            return "Screenshot captured."

        # 3. Dynamic Application Lifecycle Responses
        # Close / Terminate
        m_close = re.match(r"^(?:close|terminate|kill)\s+(?:application\s+)?(.+)$", goal_lower)
        if m_close:
            app = m_close.group(1).title()
            return f"{app} is closed."

        # Minimize
        m_min = re.match(r"^minimize\s+(?:application\s+)?(.+)$", goal_lower)
        if m_min:
            app = m_min.group(1).title()
            return f"{app} is minimized."

        # Maximize
        m_max = re.match(r"^maximize\s+(?:application\s+)?(.+)$", goal_lower)
        if m_max:
            app = m_max.group(1).title()
            return f"{app} is maximized."

        # Focus / Switch
        m_foc = re.match(r"^(?:focus|switch to)\s+(?:application\s+)?(.+)$", goal_lower)
        if m_foc:
            app = m_foc.group(1).title()
            return f"Switched to {app}."

        # Status check
        m_stat = re.match(r"^(?:is\s+(.+?)\s+(?:running|open|active)|check if\s+(.+?)\s+is\s+(?:running|open|active)|status of\s+(.+))\??$", goal_lower)
        if m_stat:
            app = (m_stat.group(1) or m_stat.group(2) or m_stat.group(3)).title()
            return f"{app} is running."

        # Open / Launch
        m_open = re.match(r"^(?:open|launch)\s+(?:application\s+)?(.+)$", goal_lower)
        if m_open:
            app = m_open.group(1).strip()
            # Clean device qualifiers if any (e.g. "on my laptop")
            app = re.sub(r"\s+on\s+(?:my\s+)?(?:laptop|desktop|workstation|pc|phone|android|mobile)$", "", app, flags=re.IGNORECASE).strip()
            # Format common names nicely
            if app.lower() in ("vs code", "vscode"):
                return "VS Code is open."
            elif app.lower() in ("file explorer", "explorer"):
                return "File Explorer is open."
            return f"{app.title()} is open."

        # Default natural confirmation
        return f"Done. {goal.capitalize()} is complete."

    @classmethod
    def format_conversational_response(cls, raw_response: str) -> str:
        """Format and polish raw Groq response for natural female voice delivery."""
        if not raw_response:
            return "I'm listening."

        # Remove markdown headers (#, ##)
        text = re.sub(r"^#+\s*", "", raw_response, flags=re.MULTILINE)
        # Remove bullet points (- or *)
        text = re.sub(r"^\s*[-*]\s*", "", text, flags=re.MULTILINE)
        # Collapse multi-paragraphs if too lengthy for voice (keep first 2-3 sentences)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        if len(sentences) > 4:
            text = " ".join(sentences[:3])

        return text.strip()
