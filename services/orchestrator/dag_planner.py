"""Structured DAG Task Planner for R.I.O.

Converts complex user intents into dependency graphs of atomic executable steps,
complete with verification strategies, retry budgets, and human approval checkpoints.
"""

from typing import Any, Dict, List, Optional
import json
import os
import re
import uuid
from packages.schemas.agents import Action, AgentRiskLevel
from packages.schemas.tasks import StepStatus, TaskPlan, TaskStep, VerificationStrategy
from services.model_router.router import ModelRouter
from services.safety.policy_engine import PolicyEngine


class DAGPlanner:
    """Generates structured DAG execution plans using Groq Reasoning & fast templates."""

    def __init__(self, policy_engine: Optional[PolicyEngine] = None, model_router: Optional[ModelRouter] = None):
        self.policy_engine = policy_engine or PolicyEngine()
        self.model_router = model_router or ModelRouter()

    async def create_plan(self, goal: str, context: Optional[Dict[str, Any]] = None) -> TaskPlan:
        """Decompose a high-level goal into a structured DAG plan."""
        goal_lower = goal.lower()
        plan_id = str(uuid.uuid4())
        steps: List[TaskStep] = []

        # 1. WhatsApp Message Sending Scenario
        if "whatsapp" in goal_lower and ("send" in goal_lower or "message" in goal_lower or "hi" in goal_lower or "hello" in goal_lower):
            contact = "Contact"
            message_text = "Hi"

            # Dynamic extraction of contact and message
            m_contact = re.search(r"(?:to contact named|to contact|to)\s+['\"]?([^'\"\.,]+)['\"]?", goal, re.IGNORECASE)
            if m_contact:
                contact = m_contact.group(1).strip()

            m_msg = re.search(r"send\s+['\"]?(.+?)['\"]?\s+to", goal, re.IGNORECASE)
            if m_msg:
                message_text = m_msg.group(1).strip()
            else:
                m_msg2 = re.search(r"(?:saying|message)\s+['\"]?(.+)['\"]?", goal, re.IGNORECASE)
                if m_msg2:
                    message_text = m_msg2.group(1).strip()

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
                action=Action(action_type="send_message", target="whatsapp_chat", parameters={"action_type": "send_message", "text": message_text, "contact": contact}),
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
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
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
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
            )
            steps = [step1, step2]

        # 3. Web Research / Browser Scenario
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
                verification_strategy=VerificationStrategy(strategy_type="dom_query", expected_state={"selector": "body"}),
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

        # 4. Application Launch Scenario (e.g. "open vs code", "open chrome", "open notepad")
        elif goal_lower.startswith("open ") or "launch " in goal_lower:
            app_target = re.sub(r"^(?:open|launch)\s+", "", goal_lower).strip()
            s1_id = str(uuid.uuid4())
            step1 = TaskStep(
                id=s1_id,
                name=f"Launch Application: {app_target.title()}",
                description=f"Launch or focus {app_target.title()} on the active workstation.",
                agent_id="computer_agent",
                action=Action(action_type="open_application", target="application", parameters={"action_type": "open_application", "app_name": app_target}),
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
                action=Action(action_type="verify_app_state", target="application", parameters={"app_name": app_target}),
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

        # 6. Dynamic LLM Planning via Groq gpt-oss-120b
        else:
            try:
                system_prompt = (
                    "You are R.I.O. Master Task Planner. Decompose the user goal into 2 to 4 atomic sequential steps.\n"
                    "Available agents: conversation_agent, planner_agent, research_agent, coding_agent, browser_agent, "
                    "computer_agent, vision_agent, document_agent, filesystem_agent, github_agent, device_agent, verification_agent, memory_agent, quantum_agent.\n"
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
                    for rs in raw_steps:
                        st_id = str(uuid.uuid4())
                        st_risk = AgentRiskLevel(rs.get("risk_level", "low").lower()) if rs.get("risk_level", "low").lower() in ("low", "medium", "high", "critical") else AgentRiskLevel.LOW
                        step_obj = TaskStep(
                            id=st_id,
                            name=rs.get("name", "Execution Step"),
                            description=rs.get("description", goal),
                            agent_id=rs.get("agent_id", "conversation_agent"),
                            action=Action(action_type=rs.get("action_type", "process"), parameters=rs.get("parameters", {})),
                            dependencies=[prev_id] if prev_id else [],
                            risk_level=st_risk,
                            verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
                        )
                        steps.append(step_obj)
                        prev_id = st_id
            except Exception:
                pass

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
