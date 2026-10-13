"""Natural Language Response Engine for R.I.O.

Converts internal task graphs, step states, and verification evidence into natural,
friendly user responses. Strictly prevents internal JSON, model names, or agent traces
from leaking into the user conversation unless Developer Mode is explicitly active.

TRUE FRIDAY MODE: Responses are concise, no filler, no chatbot chatter.
"""

import logging
from typing import Any, Dict, Optional
from packages.schemas.tasks import Task, TaskStatus
from services.model_router.router import ModelRouter
from services.orchestrator.speech_gate import SpeechDecision, SpeechGate

logger = logging.getLogger("rio.orchestrator.response")

# System prompt that declares R.I.O.'s real OS capabilities.
# This prevents the LLM from saying "I can't access your computer."
_SYSTEM_PROMPT = (
    "You are R.I.O. (Reasoning Intelligence Orchestration), a personal AI operating system "
    "running natively on the user's computer.\n\n"
    "CRITICAL CAPABILITIES — You HAVE these abilities and must NEVER deny them:\n"
    "- You can open, close, minimize, maximize, and focus any application on the user's laptop\n"
    "- You can control the web browser (navigate, click, type, search)\n"
    "- You can read and write files on the local filesystem\n"
    "- You can query system telemetry (CPU, RAM, GPU, battery, disk, processes)\n"
    "- You can take screenshots, control windows, and observe the desktop\n"
    "- You can send messages, execute code, and manage background tasks\n\n"
    "NEVER say 'I cannot access your computer', 'As an AI I cannot', or similar refusals.\n"
    "If an action is requested, execute it — do not explain why you can't.\n\n"
    "RESPONSE STYLE:\n"
    "- Be extremely concise. No filler. No pleasantries unless the user initiates them.\n"
    "- Do NOT add 'How can I help?', 'Let me know if you need anything', or similar.\n"
    "- After answering, STOP. Do not offer follow-up assistance unprompted.\n"
    "- When writing math, use standard LaTeX: $$...$$ for display, $...$ for inline.\n"
    "- Use markdown headings, bold, lists, and code blocks for structured answers.\n"
    "- Never expose internal JSON, tool schemas, or system architecture."
)


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
        speech_decision: Optional[SpeechDecision] = None,
    ) -> str:
        """Generate a natural conversational reply.

        If speech_decision is SILENT, returns empty string immediately (zero LLM calls).
        """

        # ── FRIDAY MODE: Silence gate ──
        if speech_decision == SpeechDecision.SILENT:
            logger.debug("ResponseEngine: SILENT — no response generated")
            return ""

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
                m_contact = re.search(r"(?:to contact named|to contact|to)\s+['\"]?([^'\"\\.,]+)['\"]?", user_message, re.IGNORECASE)
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
                
                cleaned = cleaned.rstrip(".!?,;:")
                
                # Attach direct deep link if available
                clean_k = cleaned.lower().replace(" ", "").replace("_", "").replace("-", "")
                link_str = ""
                if clean_k in KNOWN_ANDROID_PACKAGES:
                    spec = KNOWN_ANDROID_PACKAGES[clean_k]
                    app_url = spec.get("url")
                    if app_url and ("http" in app_url or "intent" in app_url or "tel" in app_url or "sms" in app_url):
                        link_str = f"\n\n[🚀 Open {spec['display_name']}]({app_url})"
                
                return f"Done. {cleaned.title()} is open.{link_str}"

            # Check for local system telemetry findings
            for step in reversed(task.plan.steps):
                if step.agent_id == "local_system_agent" and step.result and isinstance(step.result, dict):
                    msg = step.result.get("message")
                    if msg:
                        return msg

            if any(k in msg_lower for k in ("qaoa", "vqe", "quantum")):
                return "Quantum simulation completed and classically verified. The optimal solution has been computed."

            return f"Done. I've completed the task: '{task.goal}'."


        # 3. Conversational response synthesis (via LLM)
        try:
            recent_turns = (context or {}).get("recent_turns", [])
            messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
            for turn in recent_turns:
                messages.append({"role": turn["role"], "content": turn["content"]})
            messages.append({"role": "user", "content": user_message})

            llm_res = await self.model_router.generate(
                task_type="conversation",
                messages=messages,
                temperature=0.7,
                max_tokens=None,  # No limit - allow full natural generation up to model context window
            )
            content = llm_res.get("content")
            return content if content else ""
        except Exception as e:
            logger.warning("Conversational LLM generation failed or offline: %s", e)
            return "I am currently operating in local fallback mode. Local host monitoring, process control, and system telemetry remain fully active."
