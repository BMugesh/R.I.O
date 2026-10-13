"""Structured DAG Task Planner for R.I.O.

Converts complex user intents into dependency graphs of atomic executable steps,
complete with verification strategies, retry budgets, and human approval checkpoints.
"""

from typing import Any, Dict, List, Optional
import json
import logging
import os
import re
import uuid
from packages.schemas.agents import Action, AgentRiskLevel
from packages.schemas.devices import OriginContext
from packages.schemas.tasks import StepStatus, TaskPlan, TaskStep, VerificationStrategy
from services.device_router.router import DeviceRouter
from services.model_router.router import ModelRouter
from services.planning.plan_validator import PlanValidator
from services.safety.policy_engine import PolicyEngine

logger = logging.getLogger("rio.orchestrator.dag_planner")


class DAGPlanner:
    """Generates structured DAG execution plans using Groq Reasoning & fast templates."""

    def __init__(
        self,
        policy_engine: Optional[PolicyEngine] = None,
        model_router: Optional[ModelRouter] = None,
        device_router: Optional[DeviceRouter] = None,
    ):
        self.policy_engine = policy_engine or PolicyEngine()
        self.model_router = model_router or ModelRouter()
        self.device_router = device_router or DeviceRouter()

    async def create_plan(self, goal: str, context: Optional[Dict[str, Any]] = None) -> TaskPlan:
        """Decompose a high-level goal into a structured DAG plan."""
        goal_lower = goal.lower()
        plan_id = str(uuid.uuid4())
        steps: List[TaskStep] = []
        origin_ctx: Optional[OriginContext] = (context or {}).get("origin_context")

        # 1. WhatsApp Message Sending Scenario
        if "whatsapp" in goal_lower and ("send" in goal_lower or "message" in goal_lower or "hi" in goal_lower or "hello" in goal_lower):
            contact = "Contact"
            message_text = "Hi"

            # Dynamic extraction of contact and message
            m_contact = re.search(r"(?:to contact named|to contact|to)\s+['\"]?([^'\"\.,]+)['\"]?", goal, re.IGNORECASE)
            if m_contact:
                contact = m_contact.group(1).strip().strip("'\"")
                # Clean trailing prepositions like 'on WhatsApp'
                contact = re.sub(r"\s+(?:on|in|via|using)\s+whatsapp.*$", "", contact, flags=re.IGNORECASE).strip()

            if contact.lower() in ("myself", "me", "self", "my number", "my own number", "mugi", "mugi_13", "@mugi_13"):
                contact = "Mugi_13"

            m_msg = re.search(r"send\s+(?:msg|message)?\s*['\"]?(.+?)['\"]?\s+to", goal, re.IGNORECASE)
            if m_msg:
                message_text = m_msg.group(1).strip().strip("'\"")
            else:
                m_msg2 = re.search(r"(?:saying|message|msg)\s+['\"]?(.+)['\"]?", goal, re.IGNORECASE)
                if m_msg2:
                    message_text = m_msg2.group(1).strip().strip("'\"")
                    # Clean trailing prepositions from message text if present
                    message_text = re.sub(r"\s+(?:to\s+.+|on\s+whatsapp.*)$", "", message_text, flags=re.IGNORECASE).strip()

            route_res = self.device_router.route_action(
                prompt=goal,
                action_type="application.launch",
                parameters={"app_name": "WhatsApp"},
                origin_context=origin_ctx,
            )
            if context is not None:
                context["device_resolution"] = route_res.to_resolution()

            if route_res.target_device and route_res.target_device.platform == "android":
                s1_id = str(uuid.uuid4())
                step1 = TaskStep(
                    id=s1_id,
                    name="Launch WhatsApp on Phone",
                    description="Launch WhatsApp on the connected Android mobile runtime.",
                    agent_id="device_agent",
                    action=Action(action_type="android.launch_app", target="phone", parameters={"package": "WhatsApp", "device": "phone"}),
                    dependencies=[],
                    risk_level=AgentRiskLevel.LOW,
                    verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
                )
                s2_id = str(uuid.uuid4())
                step2 = TaskStep(
                    id=s2_id,
                    name=f"Send Message to {contact} on Phone",
                    description=f"Type '{message_text}' and dispatch to {contact} on Android.",
                    agent_id="device_agent",
                    action=Action(action_type="android.send_message", target="phone", parameters={"text": message_text, "contact": contact}),
                    dependencies=[s1_id],
                    risk_level=AgentRiskLevel.LOW,
                    verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"message_sent": True}),
                )
                s3_id = str(uuid.uuid4())
                step3 = TaskStep(
                    id=s3_id,
                    name="Verify Message Delivery",
                    description=f"Observe chat state to confirm the message checkmark appears for '{message_text}'.",
                    agent_id="verification_agent",
                    action=Action(action_type="verify_chat_delivery", target="whatsapp", parameters={"expected_text": message_text, "contact": contact}),
                    dependencies=[s2_id],
                    risk_level=AgentRiskLevel.LOW,
                    verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
                )
                steps = [step1, step2, step3]
            else:
                s1_id = str(uuid.uuid4())
                step1 = TaskStep(
                    id=s1_id,
                    name="Check Target Device Availability",
                    description="Verify desktop/laptop device is online and responsive.",
                    agent_id="device_agent",
                    action=Action(action_type="get_device_status", target="laptop", parameters={"capability": "app_management"}),
                    dependencies=[],
                    risk_level=AgentRiskLevel.LOW,
                    verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"status": "online"}),
                )

                s2_id = str(uuid.uuid4())
                step2 = TaskStep(
                    id=s2_id,
                    name="Open WhatsApp Application",
                    description="Launch or focus WhatsApp desktop client.",
                    agent_id="computer_agent",
                    action=Action(action_type="open_application", target="whatsapp", parameters={"action_type": "open_application", "app_name": "WhatsApp"}),
                    dependencies=[s1_id],
                    risk_level=AgentRiskLevel.LOW,
                    verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"window_open": True}),
                )

                s3_id = str(uuid.uuid4())
                step3 = TaskStep(
                    id=s3_id,
                    name=f"Locate Contact: {contact}",
                    description=f"Search for contact {contact} in WhatsApp interface.",
                    agent_id="computer_agent",
                    action=Action(action_type="mouse_click", target="whatsapp_search", parameters={"action_type": "mouse_click", "search_query": contact}),
                    dependencies=[s2_id],
                    risk_level=AgentRiskLevel.LOW,
                    verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"contact_selected": True}),
                )

                s4_id = str(uuid.uuid4())
                step4 = TaskStep(
                    id=s4_id,
                    name=f"Type and Send Message to {contact}",
                    description=f"Type '{message_text}' and dispatch to {contact}.",
                    agent_id="computer_agent",
                    action=Action(action_type="send_message", target="whatsapp_chat", parameters={"action_type": "send_message", "text": message_text, "contact": contact, "press_enter": True, "submit": True}),
                    dependencies=[s3_id],
                    risk_level=AgentRiskLevel.LOW,
                    verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"message_sent": True}),
                )

                s5_id = str(uuid.uuid4())
                step5 = TaskStep(
                    id=s5_id,
                    name="Verify Message Delivery",
                    description=f"Observe chat state to confirm the message checkmark appears for '{message_text}'.",
                    agent_id="verification_agent",
                    action=Action(action_type="verify_chat_delivery", target="whatsapp", parameters={"expected_text": message_text, "contact": contact}),
                    dependencies=[s4_id],
                    risk_level=AgentRiskLevel.LOW,
                    verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
                )
                steps = [step1, step2, step3, step4, step5]

        # 1b. YouTube Media Playback Scenario
        elif "youtube" in goal_lower and any(k in goal_lower for k in ("search", "play", "music", "video", "song", "relaxing")):
            import urllib.parse
            m_q = re.search(r"(?:search (?:for|google for)?|play)\s*(.+?)(?:\s*(?:and|,)\s*play.*|\s+from\s+\d+.*|\s+on\s+.*)?$", goal, re.IGNORECASE)
            query = m_q.group(1).strip() if m_q else "relaxing music"
            query = re.sub(r"^(?:for|the)\s+", "", query, flags=re.IGNORECASE).strip()
            query = query.rstrip("?.!,;:")

            if any(k in query.lower() for k in ("relaxing", "chill", "calm", "lofi", "lo-fi")):
                target_url = "https://www.youtube.com/watch?v=2OEL4P1Rz04"
            else:
                target_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"

            s1_id = str(uuid.uuid4())
            step1 = TaskStep(
                id=s1_id,
                name=f"Open YouTube in Chrome: {query.title()}",
                description=f"Launch physical Chrome browser with YouTube URL for '{query}'.",
                agent_id="computer_agent",
                action=Action(
                    action_type="open_application",
                    target="chrome",
                    parameters={
                        "action_type": "open_application",
                        "app_name": "Google Chrome",
                        "url": target_url,
                    },
                ),
                dependencies=[],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
            )
            s2_id = str(uuid.uuid4())
            step2 = TaskStep(
                id=s2_id,
                name="Verify YouTube Playback",
                description="Confirm Chrome is running and YouTube page is loaded.",
                agent_id="verification_agent",
                action=Action(action_type="verify_app_state", target="chrome", parameters={"app_name": "Google Chrome"}),
                dependencies=[s1_id],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
            )
            steps = [step1, step2]

        # 2. Screenshot Capture Scenario
        elif "screenshot" in goal_lower or "capture screen" in goal_lower:
            shot_file = os.path.join(os.getcwd(), "screenshots", "screen_latest.png")
            s1_id = str(uuid.uuid4())
            step1 = TaskStep(
                id=s1_id,
                name="Capture Screen",
                description="Capture desktop display screenshot.",
                agent_id="computer_agent",
                action=Action(action_type="screenshot", target="screen", parameters={"action_type": "screenshot", "save_path": shot_file}),
                dependencies=[],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="file_check", expected_state={"verified": True}),
            )
            s2_id = str(uuid.uuid4())
            step2 = TaskStep(
                id=s2_id,
                name="Verify Screenshot File",
                description="Verify screenshot image file exists and is valid.",
                agent_id="verification_agent",
                action=Action(action_type="verify_file", target="screenshot", parameters={"file_path": shot_file}),
                dependencies=[s1_id],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="file_check", expected_state={"verified": True}),
            )
            steps = [step1, step2]

        # 3. Coding Environment / Workspace Preparation Workflow (Rule 43 Scenario 2)
        elif any(k in goal_lower for k in ("coding environment", "ready for coding", "setup coding", "prepare workspace", "prepare my workspace", "prepare my coding environment")):
            s1_id = str(uuid.uuid4())
            step1 = TaskStep(
                id=s1_id,
                name="Inspect Host Telemetry & Windows",
                description="Inspect system resource usage and active open windows.",
                agent_id="local_system_agent",
                action=Action(action_type="system.windows.read", target="system", parameters={"action_type": "system.windows.read"}),
                dependencies=[],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="system_telemetry", expected_state={"verified": True}),
            )

            s2_id = str(uuid.uuid4())
            step2 = TaskStep(
                id=s2_id,
                name="Launch or Focus VS Code",
                description="Launch or bring VS Code to front with the current project workspace.",
                agent_id="computer_agent",
                action=Action(action_type="open_application", target="vscode", parameters={"action_type": "open_application", "app_name": "VS Code"}),
                dependencies=[s1_id],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
            )

            s3_id = str(uuid.uuid4())
            step3 = TaskStep(
                id=s3_id,
                name="Inspect Repository Structure",
                description="Check repository workspace file layout and integrity.",
                agent_id="filesystem_agent",
                action=Action(action_type="filesystem.list_dir", target="workspace", parameters={"action_type": "filesystem.list_dir", "path": "."}),
                dependencies=[s2_id],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="assertion", expected_state={"verified": True}),
            )

            s4_id = str(uuid.uuid4())
            step4 = TaskStep(
                id=s4_id,
                name="Verify Environment Readiness",
                description="Verify that editor, terminal, and workspace are fully ready for coding.",
                agent_id="verification_agent",
                action=Action(action_type="verify_readiness", target="coding_environment", parameters={"action_type": "verify_readiness", "workspace_path": "."}),
                dependencies=[s3_id],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="assertion", expected_state={"ready": True, "verified": True}),
            )
            steps = [step1, step2, step3, step4]

        # 4. YouTube Multi-Step Workflow (Search & Play on Phone or Laptop)
        elif "youtube" in goal_lower and ("search" in goal_lower or "play" in goal_lower or "music" in goal_lower or "video" in goal_lower):
            # Extract query
            q_match = re.search(r"search (?:for|google for)?\s*(.+?)(?:\s*(?:and|,)\s*play.*)?$", goal, re.IGNORECASE)
            if q_match:
                search_q = q_match.group(1).strip()
            else:
                m_play = re.search(r"play\s+(.+?)(?:\s+on\s+youtube)?$", goal, re.IGNORECASE)
                search_q = m_play.group(1).strip() if m_play else "relaxing music"

            # Clean trailing schedule phrases
            search_q = re.sub(r"\s+at\s+\d+(?::\d+)?\s*(?:am|pm)?.*$", "", search_q, flags=re.IGNORECASE).strip()

            route_res = self.device_router.route_action(
                prompt=goal,
                action_type="application.launch",
                parameters={"app_name": "YouTube"},
                origin_context=origin_ctx,
            )
            if context is not None:
                context["device_resolution"] = route_res.to_resolution()

            # Check if execution targets Android / Phone
            if route_res.target_device and route_res.target_device.platform == "android":
                s1_id = str(uuid.uuid4())
                step1 = TaskStep(
                    id=s1_id,
                    name="Open YouTube Application on Phone",
                    description="Launch YouTube application on connected Android phone.",
                    agent_id="device_agent",
                    action=Action(action_type="android.launch_app", target="phone", parameters={"package": "YouTube", "device": "phone"}),
                    dependencies=[],
                    risk_level=AgentRiskLevel.LOW,
                    verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
                )
                s2_id = str(uuid.uuid4())
                step2 = TaskStep(
                    id=s2_id,
                    name=f"Search YouTube for '{search_q}'",
                    description=f"Type '{search_q}' in search field and submit query in YouTube interface.",
                    agent_id="device_agent",
                    action=Action(action_type="android.search", target="youtube_search", parameters={"query": search_q, "package": "YouTube"}),
                    dependencies=[s1_id],
                    risk_level=AgentRiskLevel.LOW,
                    verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"results_visible": True}),
                )
                s3_id = str(uuid.uuid4())
                step3 = TaskStep(
                    id=s3_id,
                    name=f"Select and Play '{search_q}'",
                    description=f"Tap top video result and initiate playback.",
                    agent_id="device_agent",
                    action=Action(action_type="android.media.play", target="youtube_player", parameters={"item": search_q, "auto_play": True}),
                    dependencies=[s2_id],
                    risk_level=AgentRiskLevel.LOW,
                    verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"playback_state": "PLAYING"}),
                )
                s4_id = str(uuid.uuid4())
                step4 = TaskStep(
                    id=s4_id,
                    name="Verify YouTube Playback",
                    description="Observe screen state and audio stream to verify media is actively playing.",
                    agent_id="verification_agent",
                    action=Action(action_type="verify_app_state", target="youtube", parameters={"expected_state": "PLAYING", "package": "YouTube"}),
                    dependencies=[s3_id],
                    risk_level=AgentRiskLevel.LOW,
                    verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
                )
                steps = [step1, step2, step3, step4]
            else:
                # Laptop / Desktop execution
                s1_id = str(uuid.uuid4())
                step1 = TaskStep(
                    id=s1_id,
                    name="Open YouTube & Search",
                    description=f"Open browser and navigate to YouTube search for '{search_q}'.",
                    agent_id="browser_agent",
                    action=Action(action_type="browser_navigate", parameters={"url": f"https://www.youtube.com/results?search_query={search_q.replace(' ', '+')}", "query": search_q, "app": "youtube"}),
                    dependencies=[],
                    risk_level=AgentRiskLevel.LOW,
                    verification_strategy=VerificationStrategy(strategy_type="web_page", expected_state={"verified": True}),
                )
                s2_id = str(uuid.uuid4())
                step2 = TaskStep(
                    id=s2_id,
                    name=f"Play '{search_q}' Video",
                    description=f"Select top result and begin playback.",
                    agent_id="browser_agent",
                    action=Action(action_type="play_video", parameters={"query": search_q, "auto_play": True}),
                    dependencies=[s1_id],
                    risk_level=AgentRiskLevel.LOW,
                    verification_strategy=VerificationStrategy(strategy_type="dom_query", expected_state={"playback_state": "PLAYING"}),
                )
                s3_id = str(uuid.uuid4())
                step3 = TaskStep(
                    id=s3_id,
                    name="Verify Laptop Media Playback",
                    description="Confirm active video player DOM state and audio playback.",
                    agent_id="verification_agent",
                    action=Action(action_type="verify_app_state", target="browser_youtube", parameters={"app_name": "Chrome", "expected_state": "PLAYING"}),
                    dependencies=[s2_id],
                    risk_level=AgentRiskLevel.LOW,
                    verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
                )
                steps = [step1, step2, step3]

        # 4. Multi-Step Web Research & Documentation Summarization
        elif ("documentation" in goal_lower or "doc" in goal_lower or "summarize" in goal_lower) and ("search" in goal_lower or "chrome" in goal_lower or "browse" in goal_lower or "find" in goal_lower):
            q = goal
            m = re.search(r"search (?:for|google for)?\s*(.+?)(?:\s*(?:and|,)\s*(?:open|summarize).*)?$", goal, re.IGNORECASE)
            if m:
                q = m.group(1).strip()

            s1_id = str(uuid.uuid4())
            step1 = TaskStep(
                id=s1_id,
                name=f"Search Documentation: {q}",
                description=f"Open Chrome and navigate to search for '{q}'.",
                agent_id="browser_agent",
                action=Action(action_type="browser_navigate", parameters={"url": f"https://www.google.com/search?q={q.replace(' ', '+')}", "query": q}),
                dependencies=[],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="web_page", expected_state={"verified": True}),
            )
            s2_id = str(uuid.uuid4())
            step2 = TaskStep(
                id=s2_id,
                name="Fetch Documentation Content",
                description=f"Access relevant documentation portal and extract technical content for '{q}'.",
                agent_id="research_agent",
                action=Action(action_type="search_web", parameters={"query": q}),
                dependencies=[s1_id],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="assertion", expected_state={"has_results": True}),
            )
            s3_id = str(uuid.uuid4())
            step3 = TaskStep(
                id=s3_id,
                name="Synthesize Technical Summary",
                description="Synthesize extracted documentation into a structured summary.",
                agent_id="document_agent",
                action=Action(action_type="summarize_text", parameters={"topic": q}),
                dependencies=[s2_id],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="assertion", expected_state={"verified": True}),
            )
            s4_id = str(uuid.uuid4())
            step4 = TaskStep(
                id=s4_id,
                name="Verify Documentation Summary",
                description="Verify research findings are accurate and complete.",
                agent_id="verification_agent",
                action=Action(action_type="verify_documentation", target="research", parameters={"query": q}),
                dependencies=[s3_id],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
            )
            steps = [step1, step2, step3, step4]

        # 5. General Web Research Scenario
        elif "search" in goal_lower or "browse" in goal_lower or "google" in goal_lower:
            q = goal
            m = re.search(r"search (?:for|google for)?\s*(.+)", goal, re.IGNORECASE)
            if m:
                q = m.group(1).strip()
            s1_id = str(uuid.uuid4())
            step1 = TaskStep(
                id=s1_id,
                name="Open Chrome & Navigate",
                description=f"Open browser and navigate to search: {q}",
                agent_id="browser_agent",
                action=Action(action_type="browser_navigate", parameters={"url": f"https://www.google.com/search?q={q}"}),
                dependencies=[],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="web_page", expected_state={"url": f"https://www.google.com/search?q={q}"}),
            )
            s2_id = str(uuid.uuid4())
            step2 = TaskStep(
                id=s2_id,
                name=f"Extract Findings: {q}",
                description=f"Extract and summarize search results for {q}.",
                agent_id="research_agent",
                action=Action(action_type="search_web", parameters={"query": q}),
                dependencies=[s1_id],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="assertion", expected_state={"has_results": True}),
            )
            steps = [step1, step2]

        # 4. Multi-Device Compound Task (e.g. "open chrome on my phone and vs code on my laptop")
        elif ("on my phone" in goal_lower or "on phone" in goal_lower) and ("on my laptop" in goal_lower or "on laptop" in goal_lower or "on workstation" in goal_lower):
            # Extract phone app and laptop app
            phone_match = re.search(r"(?:open|launch)\s+([a-zA-Z0-9\-_]+(?:\s+[a-zA-Z0-9\-_]+)?)\s+on\s+(?:my\s+)?phone", goal, re.IGNORECASE)
            laptop_match = re.search(r"(?:then\s+open|and\s+open|open|launch)\s+([a-zA-Z0-9\-_]+(?:\s+[a-zA-Z0-9\-_]+)?)\s+on\s+(?:my\s+)?(?:laptop|workstation|pc|desktop)", goal, re.IGNORECASE)
            
            phone_app = phone_match.group(1).strip() if phone_match else "Chrome"
            laptop_app = laptop_match.group(1).strip() if laptop_match else "VS Code"

            s1_id = str(uuid.uuid4())
            step1 = TaskStep(
                id=s1_id,
                name=f"Launch {phone_app.title()} on Phone",
                description=f"Launch {phone_app.title()} on the connected Android phone runtime.",
                agent_id="device_agent",
                action=Action(action_type="android.launch_app", target="phone", parameters={"package": phone_app, "device": "phone"}),
                dependencies=[],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
            )
            s2_id = str(uuid.uuid4())
            step2 = TaskStep(
                id=s2_id,
                name=f"Launch {laptop_app.title()} on Laptop",
                description=f"Launch {laptop_app.title()} on the connected Windows workstation runtime.",
                agent_id="computer_agent",
                action=Action(action_type="open_application", target="laptop", parameters={"action_type": "open_application", "app_name": laptop_app}),
                dependencies=[s1_id],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
            )
            s3_id = str(uuid.uuid4())
            step3 = TaskStep(
                id=s3_id,
                name="Verify Multi-Device State",
                description="Verify successful execution and active state across both runtimes.",
                agent_id="verification_agent",
                action=Action(action_type="verify_app_state", target="multi_device", parameters={"phone_app": phone_app, "laptop_app": laptop_app}),
                dependencies=[s2_id],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
            )
            steps = [step1, step2, step3]

        # 5. Camera / Photo Capture Scenario
        elif "take a photo" in goal_lower or "capture photo" in goal_lower or "take a picture" in goal_lower or "camera" in goal_lower:
            route_res = self.device_router.route_action(
                prompt=goal,
                action_type="camera.capture",
                parameters={"facing": "back"},
                origin_context=origin_ctx,
            )
            if context is not None:
                context["device_resolution"] = route_res.to_resolution()

            if route_res.error:
                s1_id = str(uuid.uuid4())
                step1 = TaskStep(
                    id=s1_id,
                    name="Camera Capability Diagnostic",
                    description=route_res.error,
                    agent_id="conversation_agent",
                    action=Action(action_type="error_diagnostic", parameters={"error": route_res.error}),
                    dependencies=[],
                    risk_level=AgentRiskLevel.LOW,
                )
                return TaskPlan(id=plan_id, goal=goal, steps=[step1], estimated_duration_seconds=1.0)

            s1_id = str(uuid.uuid4())
            step1 = TaskStep(
                id=s1_id,
                name="Capture Camera Photo",
                description="Capture photo using mobile camera sensor runtime.",
                agent_id="device_agent",
                action=Action(action_type="camera.capture", target="camera", parameters={"facing": "back", "device_id": route_res.target_device.device_id if route_res.target_device else "phone-01"}),
                dependencies=[],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
            )
            s2_id = str(uuid.uuid4())
            step2 = TaskStep(
                id=s2_id,
                name="Verify Captured Photo",
                description="Verify photo was written to storage and media URI is valid.",
                agent_id="verification_agent",
                action=Action(action_type="verify_file", target="camera_photo", parameters={"photo": True}),
                dependencies=[s1_id],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
            )
            steps = [step1, step2]

        # 5b. Multi-Step: VS Code + Project + Test Suite
        elif ("vs code" in goal_lower or "vscode" in goal_lower) and ("test" in goal_lower or "run" in goal_lower) and ("project" in goal_lower or "rio" in goal_lower or "codebase" in goal_lower):
            s1_id = str(uuid.uuid4())
            step1 = TaskStep(
                id=s1_id,
                name="Launch VS Code with Project",
                description="Launch VS Code and open project workspace directory.",
                agent_id="computer_agent",
                action=Action(action_type="open_application", target="vscode", parameters={"action_type": "open_application", "app_name": "VS Code"}),
                dependencies=[],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"window_open": True}),
            )
            s2_id = str(uuid.uuid4())
            step2 = TaskStep(
                id=s2_id,
                name="Execute Test Suite",
                description="Run project unit and integration test suite via local terminal.",
                agent_id="coding_agent",
                action=Action(action_type="run_tests", parameters={"command": "pytest"}),
                dependencies=[s1_id],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="assertion", expected_state={"tests_passed": True}),
            )
            s3_id = str(uuid.uuid4())
            step3 = TaskStep(
                id=s3_id,
                name="Verify Test Results",
                description="Verify test suite completion and resource reclamation.",
                agent_id="verification_agent",
                action=Action(action_type="verify_file", target="test_results", parameters={"verified": True}),
                dependencies=[s2_id],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
            )
            steps = [step1, step2, step3]

        # 5c. Multi-Step: Spotify Playback
        elif "spotify" in goal_lower and ("play" in goal_lower or "song" in goal_lower or "playlist" in goal_lower or "music" in goal_lower):
            playlist_name = "music"
            m_pl = re.search(r"play\s+['\"]?(.+?)['\"]?(?:\s+on\s+spotify)?$", goal, re.IGNORECASE)
            if m_pl:
                playlist_name = m_pl.group(1).strip()

            s1_id = str(uuid.uuid4())
            step1 = TaskStep(
                id=s1_id,
                name="Launch Spotify Client",
                description="Launch or bring Spotify desktop player to foreground.",
                agent_id="computer_agent",
                action=Action(action_type="open_application", target="spotify", parameters={"action_type": "open_application", "app_name": "Spotify"}),
                dependencies=[],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"window_open": True}),
            )
            s2_id = str(uuid.uuid4())
            step2 = TaskStep(
                id=s2_id,
                name=f"Search and Play: {playlist_name}",
                description=f"Type '{playlist_name}' and trigger playback in Spotify.",
                agent_id="computer_agent",
                action=Action(action_type="application.control", target="spotify", parameters={"action_type": "application.control", "query": playlist_name, "app_name": "Spotify"}),
                dependencies=[s1_id],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"playback_state": "PLAYING"}),
            )
            s3_id = str(uuid.uuid4())
            step3 = TaskStep(
                id=s3_id,
                name="Verify Media Playback",
                description="Confirm audio playback and media session state.",
                agent_id="verification_agent",
                action=Action(action_type="verify_app_state", target="spotify", parameters={"app_name": "Spotify", "expected_state": "PLAYING"}),
                dependencies=[s2_id],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
            )
            steps = [step1, step2, step3]

        # 5d. Multi-Step: File Explorer Navigation
        elif ("explorer" in goal_lower or "file explorer" in goal_lower or "folder" in goal_lower) and ("open" in goal_lower or "go to" in goal_lower or "navigate" in goal_lower):
            folder_target = "project"
            m_f = re.search(r"(?:open|go to|navigate to)\s+(?:my\s+)?(.+?)(?:\s+in\s+(?:file\s+)?explorer)?$", goal, re.IGNORECASE)
            if m_f:
                folder_target = m_f.group(1).strip()

            s1_id = str(uuid.uuid4())
            step1 = TaskStep(
                id=s1_id,
                name=f"Open File Explorer: {folder_target.title()}",
                description=f"Launch File Explorer positioned at {folder_target}.",
                agent_id="computer_agent",
                action=Action(action_type="open_application", target="explorer", parameters={"action_type": "open_application", "app_name": "File Explorer", "folder": folder_target}),
                dependencies=[],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"window_open": True}),
            )
            s2_id = str(uuid.uuid4())
            step2 = TaskStep(
                id=s2_id,
                name="Verify File Explorer Window",
                description="Confirm File Explorer window is open and focused.",
                agent_id="verification_agent",
                action=Action(action_type="verify_app_state", target="explorer", parameters={"app_name": "File Explorer"}),
                dependencies=[s1_id],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
            )
            steps = [step1, step2]

        # 5e. Application Management: Close
        elif goal_lower.startswith("close ") or "terminate " in goal_lower or "kill " in goal_lower:
            m_close = re.search(r"^(?:close|terminate|kill)\s+(.+?)$", goal, re.IGNORECASE)
            target_to_close = m_close.group(1).strip() if m_close else "application"
            s1_id = str(uuid.uuid4())
            step1 = TaskStep(
                id=s1_id,
                name=f"Close Application: {target_to_close.title()}",
                description=f"Gracefully close {target_to_close.title()} window.",
                agent_id="computer_agent",
                action=Action(action_type="close_application", target="application", parameters={"action_type": "close_application", "app_name": target_to_close}),
                dependencies=[],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
            )
            steps = [step1]

        # 5f. Application Management: Focus / Switch / Minimize / Maximize
        elif goal_lower.startswith(("focus ", "switch to ", "minimize ", "maximize ")):
            m_act = re.match(r"^(focus|switch to|minimize|maximize)\s+(.+?)$", goal, re.IGNORECASE)
            action_word = m_act.group(1).lower().strip() if m_act else "focus"
            app_to_manage = m_act.group(2).strip() if m_act else "application"

            action_name = "application.focus"
            if "minimize" in action_word:
                action_name = "application.minimize"
            elif "maximize" in action_word:
                action_name = "application.maximize"

            s1_id = str(uuid.uuid4())
            step1 = TaskStep(
                id=s1_id,
                name=f"{action_word.title()} {app_to_manage.title()}",
                description=f"{action_word.title()} {app_to_manage.title()} window.",
                agent_id="computer_agent",
                action=Action(action_type=action_name, target="application", parameters={"action_type": action_name, "app_name": app_to_manage}),
                dependencies=[],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
            )
            steps = [step1]

        # 5g. Application Management: Status Query
        elif goal_lower.startswith(("status of ", "check if ", "is ")) and any(k in goal_lower for k in ("running", "open", "active", "status")):
            m_stat = re.search(r"^(?:status of|check if|is)\s+(.+?)(?:\s+(?:running|open|active|status))?\??$", goal, re.IGNORECASE)
            app_stat = m_stat.group(1).strip() if m_stat else "application"
            app_stat = re.sub(r"\s+is$", "", app_stat, flags=re.IGNORECASE).strip()
            s1_id = str(uuid.uuid4())
            step1 = TaskStep(
                id=s1_id,
                name=f"Check Status: {app_stat.title()}",
                description=f"Query running status and window data for {app_stat.title()}.",
                agent_id="computer_agent",
                action=Action(action_type="application.status", target="application", parameters={"action_type": "application.status", "app_name": app_stat}),
                dependencies=[],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
            )
            steps = [step1]

        # 6. General Application Launch Scenario (Origin-Bound or Explicit Remote)
        elif (clean_goal := re.sub(r"^(?:can|could|would|will)\s+you\s+(?:please\s+)?|^(?:please|kindly)\s+|^(?:i\s+want\s+you\s+to|i\s+need\s+you\s+to)\s+", "", goal_lower).strip()) and (clean_goal.startswith("open ") or "launch " in clean_goal):
            # Extract application name
            m_app = re.search(r"^(?:open|launch)\s+(.+?)(?:\s+on\s+(?:my\s+)?(?:phone|android|mobile|pixel|laptop|desktop|workstation|pc|server))?$", clean_goal, re.IGNORECASE)
            if m_app:
                app_target = m_app.group(1).strip()
            else:
                app_target = re.sub(r"^(?:open|launch)\s+", "", clean_goal, flags=re.IGNORECASE).strip()

            # Clean trailing device qualifiers if still in target
            app_target = re.sub(r"\s+on\s+(?:my\s+)?(?:laptop|desktop|workstation|pc|phone|android|mobile|server)$", "", app_target, flags=re.IGNORECASE).strip()
            app_target = app_target.rstrip("?.!,;:")

            # Check for desktop-only apps on mobile origin without explicit device target
            desktop_only_apps = {"vs code", "vscode", "visual studio code", "pycharm", "intellij", "docker", "postman", "gitkraken"}
            is_desktop_only = app_target.lower() in desktop_only_apps

            is_mobile_origin = False
            if origin_ctx:
                itype = origin_ctx.interface_type.value if hasattr(origin_ctx.interface_type, "value") else str(origin_ctx.interface_type).lower()
                is_mobile_origin = (
                    origin_ctx.origin_device_id == "phone-01"
                    or origin_ctx.origin_platform == "android"
                    or itype in ("android", "ios", "mobile")
                )

            has_explicit_laptop_target = any(k in goal_lower for k in ("on my laptop", "on laptop", "on desktop", "on workstation", "on pc", "on windows"))

            if is_mobile_origin and is_desktop_only and not has_explicit_laptop_target:
                # SAFETY BOUNDARY: Do NOT silently redirect! Fail safely with clear diagnostic.
                s1_id = str(uuid.uuid4())
                dev_id_str = origin_ctx.origin_device_id or "phone-01"
                diag_msg = f"Origin device '{dev_id_str}' (Android) does not support desktop application '{app_target.title()}'. To run on your laptop, please specify 'Open {app_target.title()} on my laptop'."
                step1 = TaskStep(
                    id=s1_id,
                    name="Capability Check Failed",
                    description=diag_msg,
                    agent_id="conversation_agent",
                    action=Action(action_type="error_diagnostic", parameters={"error": diag_msg}),
                    dependencies=[],
                    risk_level=AgentRiskLevel.LOW,
                )
                return TaskPlan(id=plan_id, goal=goal, steps=[step1], estimated_duration_seconds=1.0)

            # Route action via DeviceRouter
            route_res = self.device_router.route_action(
                prompt=goal,
                action_type="application.launch",
                parameters={"app_name": app_target},
                origin_context=origin_ctx,
            )
            if context is not None:
                context["device_resolution"] = route_res.to_resolution()

            if route_res.error:
                s1_id = str(uuid.uuid4())
                step1 = TaskStep(
                    id=s1_id,
                    name="Device Resolution Diagnostic",
                    description=route_res.error,
                    agent_id="conversation_agent",
                    action=Action(action_type="error_diagnostic", parameters={"error": route_res.error}),
                    dependencies=[],
                    risk_level=AgentRiskLevel.LOW,
                )
                return TaskPlan(id=plan_id, goal=goal, steps=[step1], estimated_duration_seconds=1.0)

            if route_res.target_device and route_res.target_device.platform == "android":
                s1_id = str(uuid.uuid4())
                step1 = TaskStep(
                    id=s1_id,
                    name=f"Launch {app_target.title()} on Phone",
                    description=f"Dispatch Intent to launch {app_target.title()} on Android mobile runtime.",
                    agent_id="device_agent",
                    action=Action(action_type="android.launch_app", target="phone", parameters={"package": app_target, "device": "phone", "device_id": route_res.target_device.device_id}),
                    dependencies=[],
                    risk_level=AgentRiskLevel.LOW,
                    verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
                )
                s2_id = str(uuid.uuid4())
                step2 = TaskStep(
                    id=s2_id,
                    name=f"Verify {app_target.title()} Package State",
                    description=f"Observe package and activity state to verify {app_target.title()} is in foreground.",
                    agent_id="verification_agent",
                    action=Action(action_type="verify_app_state", target="phone", parameters={"package": app_target, "device_id": route_res.target_device.device_id}),
                    dependencies=[s1_id],
                    risk_level=AgentRiskLevel.LOW,
                    verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
                )
                steps = [step1, step2]
            else:
                target_dev_id = route_res.target_device.device_id if route_res.target_device else "laptop-01"
                s1_id = str(uuid.uuid4())
                step1 = TaskStep(
                    id=s1_id,
                    name=f"Launch Application: {app_target.title()}",
                    description=f"Launch or focus {app_target.title()} on the active workstation.",
                    agent_id="computer_agent",
                    action=Action(action_type="open_application", target="application", parameters={"action_type": "open_application", "app_name": app_target, "device_id": target_dev_id}),
                    dependencies=[],
                    risk_level=AgentRiskLevel.LOW,
                    verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
                )
                s2_id = str(uuid.uuid4())
                step2 = TaskStep(
                    id=s2_id,
                    name=f"Verify {app_target.title()} State",
                    description=f"Verify that {app_target.title()} is active and focused.",
                    agent_id="verification_agent",
                    action=Action(action_type="verify_app_state", target="application", parameters={"app_name": app_target, "device_id": target_dev_id}),
                    dependencies=[s1_id],
                    risk_level=AgentRiskLevel.LOW,
                    verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
                )
                steps = [step1, step2]


        # 5. Quantum Computing Scenario
        elif any(k in goal_lower for k in ("qaoa", "vqe", "quantum", "maxcut")):
            s1_id = str(uuid.uuid4())
            step1 = TaskStep(
                id=s1_id,
                name="Formulate Quantum Problem",
                description="Construct Hamiltonian / circuit spec for problem.",
                agent_id="quantum_agent",
                action=Action(action_type="formulate_hamiltonian", parameters={"goal": goal}),
                dependencies=[],
                risk_level=AgentRiskLevel.LOW,
            )
            s2_id = str(uuid.uuid4())
            step2 = TaskStep(
                id=s2_id,
                name="Execute Quantum Simulation",
                description="Run circuit simulation using Qiskit Aer.",
                agent_id="quantum_agent",
                action=Action(action_type="execute_circuit", parameters={"backend": "aer_simulator"}),
                dependencies=[s1_id],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="assertion", expected_state={"verified": True}),
            )
            steps = [step1, step2]

        # 5.1 Local System Telemetry Scenario
        elif any(k in goal_lower for k in (
            "what time", "what's the time", "current time", "what date", "today's date",
            "what gpu", "my gpu", "show gpu", "gpu usage", "gpu temp", "vram",
            "what ram", "my ram", "ram usage", "memory usage", "free memory", "how much ram", "free ram", "how much memory", "ram is free",
            "cpu usage", "cpu load", "how many cores",
            "battery level", "battery status", "plugged in",
            "disk space", "storage space", "free space",
            "open windows", "active windows", "what windows are open",
            "what os", "windows version", "system status", "system summary"
        )):
            s1_id = str(uuid.uuid4())
            step1 = TaskStep(
                id=s1_id,
                name="Read System Telemetry",
                description=f"Query local hardware and OS telemetry for '{goal}'.",
                agent_id="local_system_agent",
                action=Action(action_type="system.telemetry", parameters={"query": goal}),
                dependencies=[],
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
            )
            steps = [step1]

        # 6. Dynamic LLM Planning via Groq gpt-oss-120b
        else:
            try:
                system_prompt = (
                    "You are R.I.O. Master Task Planner. Decompose the user goal into 2 to 4 atomic sequential steps.\n"
                    "Available agents: conversation_agent, planner_agent, research_agent, coding_agent, browser_agent, "
                    "computer_agent, vision_agent, document_agent, filesystem_agent, github_agent, device_agent, verification_agent, memory_agent, quantum_agent, local_system_agent.\n"
                    "Output valid JSON ONLY in this format:\n"
                    "{\"steps\": [{\"name\": \"...\", \"description\": \"...\", \"agent_id\": \"...\", \"action_type\": \"...\", \"parameters\": {}, \"risk_level\": \"low\"}]}"
                )
                llm_plan = await self.model_router.generate(
                    task_type="planning",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": goal},
                    ],
                    max_tokens=500,
                )
                content = llm_plan.get("content", "")
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if json_match:
                    plan_dict = json.loads(json_match.group(0))
                    raw_steps = plan_dict.get("steps", [])
                    prev_id = None
                    candidate_steps = []
                    for rs in raw_steps:
                        st_id = str(uuid.uuid4())
                        st_risk = AgentRiskLevel(rs.get("risk_level", "low").lower()) if rs.get("risk_level", "low").lower() in ("low", "medium", "high", "critical") else AgentRiskLevel.LOW
                        rs_agent = rs.get("agent_id", "conversation_agent")
                        if rs_agent in ("computer_agent", "device_agent"):
                            strat_type = "device_observation"
                        elif rs_agent in ("browser_agent",):
                            strat_type = "web_page"
                        elif rs_agent in ("filesystem_agent",):
                            strat_type = "file_check"
                        elif rs_agent in ("local_system_agent",):
                            strat_type = "system_telemetry"
                        else:
                            strat_type = "assertion"

                        step_obj = TaskStep(
                            id=st_id,
                            name=rs.get("name", "Execution Step"),
                            description=rs.get("description", goal),
                            agent_id=rs_agent,
                            action=Action(action_type=rs.get("action_type", "process"), parameters=rs.get("parameters", {})),
                            dependencies=[prev_id] if prev_id else [],
                            risk_level=st_risk,
                            verification_strategy=VerificationStrategy(strategy_type=strat_type, expected_state={"verified": True}),
                        )
                        candidate_steps.append(step_obj)
                        prev_id = st_id

                    # Validate candidate steps via PlanValidator
                    candidate_plan = TaskPlan(id=plan_id, goal=goal, steps=candidate_steps, estimated_duration_seconds=len(candidate_steps) * 2.0)
                    val_res = PlanValidator.validate(candidate_plan, context=context)
                    if val_res.is_valid:
                        steps = candidate_steps
                    else:
                        logger.warning(f"LLM generated plan failed validation: {val_res.errors}")
            except Exception as e:
                logger.warning(f"Dynamic LLM planning failed, falling back to default plan: {e}")

            if not steps:
                s1_id = str(uuid.uuid4())
                step1 = TaskStep(
                    id=s1_id,
                    name="Execute Action",
                    description=goal,
                    agent_id="conversation_agent",
                    action=Action(action_type="process", parameters={"query": goal}),
                    dependencies=[],
                    risk_level=AgentRiskLevel.LOW,
                )
                steps = [step1]

        # Check approval requirements on steps
        for s in steps:
            if self.policy_engine.requires_approval(s.risk_level):
                s.requires_approval = True

        return TaskPlan(id=plan_id, goal=goal, steps=steps, estimated_duration_seconds=len(steps) * 2.0)
