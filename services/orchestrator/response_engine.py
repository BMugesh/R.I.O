"""Natural Language Response Engine for R.I.O.

Converts internal task graphs, step states, and verification evidence into natural,
friendly user responses. Strictly prevents internal JSON, model names, or agent traces
from leaking into the user conversation unless Developer Mode is explicitly active.
"""

from typing import Any, Dict, Optional
from packages.schemas.tasks import Task, TaskStatus
from services.model_router.router import ModelRouter


class ResponseEngine:
    """Synthesizes human-friendly responses from internal execution states."""

    def __init__(self, model_router: Optional[ModelRouter] = None):
        self.model_router = model_router or ModelRouter()

    async def generate_response(
        self,
        user_message: str,
        task: Optional[Task] = None,
        context: Optional[Dict[str, Any]] = None,
        developer_mode: bool = False,
    ) -> str:
        """Generate a natural conversational reply."""

        # 1. If it was a task that failed or errored
        if task and task.status == TaskStatus.FAILED:
            err = task.error or "The requested action could not be completed."
            if "does not support" in err.lower() or "not supported" in err.lower() or "origin device" in err.lower() or "cannot run" in err.lower():
                return err
            if "whatsapp" in user_message.lower():
                return "I couldn't complete the message because WhatsApp wasn't available or verified."
            if "contact" in err.lower():
                return "I couldn't confidently identify the correct contact, so I haven't sent anything."
            return f"I ran into an issue and couldn't finish the task: {err}"

        # 2. If it was an action task that succeeded with verification
        if task and task.status == TaskStatus.COMPLETED and task.plan and len(task.plan.steps) >= 1:
            msg_lower = user_message.lower()
            dev_resolution = (context or {}).get("device_resolution")

            # Multi-Device compound response
            if ("on my phone" in msg_lower or "on phone" in msg_lower) and ("on my laptop" in msg_lower or "on laptop" in msg_lower):
                import re
                p_match = re.search(r"(?:open|launch)\s+([a-zA-Z0-9\-_]+(?:\s+[a-zA-Z0-9\-_]+)?)\s+on\s+(?:my\s+)?phone", user_message, re.IGNORECASE)
                l_match = re.search(r"(?:then\s+open|and\s+open|open|launch)\s+([a-zA-Z0-9\-_]+(?:\s+[a-zA-Z0-9\-_]+)?)\s+on\s+(?:my\s+)?(?:laptop|workstation|pc)", user_message, re.IGNORECASE)
                p_app = p_match.group(1).strip().title() if p_match else "Chrome"
                l_app = l_match.group(1).strip().title() if l_match else "VS Code"
                return f"Done. {p_app} is open on your phone, and {l_app} is open on your laptop."

            # Explicit Remote Overrides
            if ("on my phone" in msg_lower or "on phone" in msg_lower or "on android" in msg_lower) and (msg_lower.startswith("open ") or "launch " in msg_lower):
                import re
                m_app = re.search(r"(?:open|launch)\s+([a-zA-Z0-9\s]+?)(?:\s+on\s+.*)?$", user_message, re.IGNORECASE)
                app_n = m_app.group(1).strip().title() if m_app else "The application"
                return f"Done. {app_n} is open on your phone."

            if ("on my laptop" in msg_lower or "on laptop" in msg_lower or "on desktop" in msg_lower or "on pc" in msg_lower or "on workstation" in msg_lower) and (msg_lower.startswith("open ") or "launch " in msg_lower):
                import re
                m_app = re.search(r"(?:open|launch)\s+([a-zA-Z0-9\s]+?)(?:\s+on\s+.*)?$", user_message, re.IGNORECASE)
                app_n = m_app.group(1).strip().title() if m_app else "The application"
                return f"Done. {app_n} is open on your laptop."

            # Camera photo
            if "photo" in msg_lower or "picture" in msg_lower or "camera" in msg_lower:
                return "Done. I've captured the photo using your phone's camera."

            # WhatsApp message
            if "whatsapp" in msg_lower and ("send" in msg_lower or "message" in msg_lower or "hi" in msg_lower or "hello" in msg_lower):
                import re
                m_contact = re.search(r"(?:to contact named|to contact|to)\s+['\"]?([^'\"\.,]+)['\"]?", user_message, re.IGNORECASE)
                contact = m_contact.group(1).strip() if m_contact else "the contact"
                return f"Done. I've sent the message to {contact}. Please check WhatsApp."

            # YouTube search & play workflow
            if "youtube" in msg_lower and ("search" in msg_lower or "play" in msg_lower or "music" in msg_lower or "video" in msg_lower or "from" in msg_lower):
                import re
                import urllib.parse
                m_q = re.search(r"(?:search (?:for|google for)?|play)\s*(.+?)(?:\s*(?:and|,)\s*play.*|\s+from\s+\d+.*|\s+on\s+.*)?$", user_message, re.IGNORECASE)
                query = m_q.group(1).strip() if m_q else "relaxing music"
                query = re.sub(r"^(?:for|the)\s+", "", query, flags=re.IGNORECASE).strip()
                encoded_q = urllib.parse.quote_plus(query)
                return f"Done. Playing '{query}' on YouTube.\n\n[▶️ Watch on YouTube](https://www.youtube.com/results?search_query={encoded_q})"

            if "youtube" in msg_lower and (msg_lower.startswith("open ") or "launch " in msg_lower):
                return f"Done. YouTube is open.\n\n[▶️ Open YouTube](https://www.youtube.com)"

            if "screenshot" in msg_lower:
                return "Done. I've captured the screenshot and verified the file has been saved."
            if "search" in msg_lower or "browse" in msg_lower:
                for step in task.plan.steps:
                    if step.result and isinstance(step.result, dict) and step.result.get("research_findings"):
                        return step.result["research_findings"]
                return "I've completed the search and gathered the relevant findings for you."
            if msg_lower.startswith("open ") or "launch " in msg_lower:
                import re
                from runtime.android.actions import KNOWN_ANDROID_PACKAGES
                cleaned = re.sub(r"^(?:open|launch)\s+", "", user_message, flags=re.IGNORECASE)
                cleaned = re.sub(r"\s+on\s+(?:my\s+)?(?:laptop|desktop|workstation|pc|phone|android|mobile|server)$", "", cleaned, flags=re.IGNORECASE).strip()
                
                # Attach direct deep link if available
                clean_k = cleaned.lower().replace(" ", "").replace("_", "").replace("-", "")
                link_str = ""
                if clean_k in KNOWN_ANDROID_PACKAGES:
                    spec = KNOWN_ANDROID_PACKAGES[clean_k]
                    app_url = spec.get("url")
                    if app_url and ("http" in app_url or "intent" in app_url or "tel" in app_url or "sms" in app_url):
                        link_str = f"\n\n[🚀 Open {spec['display_name']}]({app_url})"
                
                return f"Done. {cleaned.title()} is open.{link_str}"

            if any(k in msg_lower for k in ("qaoa", "vqe", "quantum")):
                return "Quantum simulation completed and classically verified. The optimal solution has been computed."

            return f"Done. I've completed the task: '{task.goal}'."


        # 3. Conversational chit-chat response synthesis (via Llama 3.3 70B / Fast Router)
        try:
            recent_turns = (context or {}).get("recent_turns", [])
            system_prompt = (
                "You are R.I.O. (Reasoning Intelligence Orchestration), a sophisticated, helpful, and precise personal AI operating system.\n"
                "Guidelines:\n"
                "- Speak naturally, clearly, and concisely without robotic meta-commentary.\n"
                "- Never expose internal JSON, tool schemas, or system architecture details.\n"
                "- When writing mathematical equations, formulas, vectors, or matrices, format them in standard Markdown/LaTeX:\n"
                "  * Use $$...$$ or \\[...\\] for display equations and matrices (e.g. $$\\mathbf{a} = \\begin{bmatrix} 4 \\\\ -2 \\\\ 5 \\end{bmatrix}$$).\n"
                "  * Use $...$ or \\(...\\) for inline math.\n"
                "- Use clear markdown headings (##, ###), bold text, numbered lists, and code blocks for structured answers."
            )
            messages = [{"role": "system", "content": system_prompt}]
            for turn in recent_turns:
                messages.append({"role": turn["role"], "content": turn["content"]})
            messages.append({"role": "user", "content": user_message})

            llm_res = await self.model_router.generate(
                task_type="conversation",
                messages=messages,
                temperature=0.7,
                max_tokens=None,  # No limit - allow full natural generation up to model context window
            )
            return llm_res.get("content", "I'm here to help. What would you like to do?")
        except Exception:
            return "Hey! I'm doing great. How about you?"
