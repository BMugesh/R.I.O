"""Task Decomposer for R.I.O. (Milestone 5).

Decomposes complex, multi-clause objectives into parallelizable and sequential
subtasks, marking concurrency flags and dependencies appropriately.
"""

import re
from typing import Any, Dict, List, Optional
import uuid

from packages.schemas.agents import Action, AgentRiskLevel
from packages.schemas.tasks import TaskStep, VerificationStrategy
from services.planning.plan_models import TaskAnalysis


class TaskDecomposer:
    """Decomposes compound objectives into structured TaskStep graphs."""

    @staticmethod
    def decompose_parallel_research(goal: str, analysis: TaskAnalysis) -> Optional[List[TaskStep]]:
        """Identify multi-target research or inspection tasks that can run in parallel."""
        goal_lower = goal.lower()

        # 1. First check explicit laptop comparison pattern:
        # e.g. "Research the latest NVIDIA GPU, compare it with my laptop and create a report."
        if "gpu" in goal_lower and ("laptop" in goal_lower or "local" in goal_lower) and "compare" in goal_lower:
            s1_id = str(uuid.uuid4())
            s1 = TaskStep(
                id=s1_id,
                name="Research Latest GPU",
                description="Gather specifications, benchmarks, and architectural details for latest GPUs.",
                agent_id="research_agent",
                action=Action(action_type="web_search", parameters={"query": "latest NVIDIA GPU specs benchmarks"}),
                dependencies=[],
                parallelizable=True,
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="assertion", expected_state={"verified": True}),
            )

            s2_id = str(uuid.uuid4())
            s2 = TaskStep(
                id=s2_id,
                name="Inspect Local Hardware",
                description="Inspect host system GPU, VRAM, and hardware specifications.",
                agent_id="computer_agent",
                action=Action(action_type="hardware_inspection", parameters={"component": "gpu"}),
                dependencies=[],
                parallelizable=True,
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="device_observation", expected_state={"verified": True}),
            )

            s3_id = str(uuid.uuid4())
            s3 = TaskStep(
                id=s3_id,
                name="Synthesize Hardware Comparison",
                description="Compare remote GPU benchmarks against local laptop GPU specs.",
                agent_id="research_agent",
                action=Action(action_type="synthesize_comparison", parameters={"sources": [s1_id, s2_id]}),
                dependencies=[s1_id, s2_id],
                parallelizable=False,
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="assertion", expected_state={"verified": True}),
            )

            s4_id = str(uuid.uuid4())
            s4 = TaskStep(
                id=s4_id,
                name="Generate Comparison Report",
                description="Format comparison findings into final report.",
                agent_id="document_agent",
                action=Action(action_type="create_document", parameters={"title": "GPU Comparison Report", "source": s3_id}),
                dependencies=[s3_id],
                parallelizable=False,
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="file_check", expected_state={"file_path": "report.md"}),
            )
            return [s1, s2, s3, s4]

        # 2. Check for multi-target pattern: e.g. "research X, Y and Z", "compare X and Y", "check A, B, and C"
        m_comp = re.search(r"(?:research|compare|check|analyze|inspect)\s+(.+?)(?:\s+and\s+(?:create|write|generate|output)\s+a?\s*report)?$", goal, re.IGNORECASE)
        if not m_comp:
            return None

        body = m_comp.group(1).strip()
        # Extract items separated by commas and/or 'and'
        items = re.split(r",\s*(?:and\s+)?|\s+and\s+", body)
        items = [item.strip(" .") for item in items if item.strip(" .") and item.strip(" .").lower() not in ("them", "it", "laptop", "pc")]

        if len(items) < 2:
            return None

        # Build parallel steps for each item
        parallel_steps: List[TaskStep] = []
        for idx, item in enumerate(items):
            sid = str(uuid.uuid4())
            step = TaskStep(
                id=sid,
                name=f"Research {item.capitalize()}",
                description=f"Conduct focused research and data gathering on '{item}'.",
                agent_id="research_agent",
                action=Action(action_type="web_search", parameters={"query": item}),
                dependencies=[],
                parallelizable=True,
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="assertion", expected_state={"verified": True}),
            )
            parallel_steps.append(step)

        # Merge / Comparison step
        dep_ids = [s.id for s in parallel_steps]
        merge_id = str(uuid.uuid4())
        merge_step = TaskStep(
            id=merge_id,
            name=f"Compare {', '.join(items)}",
            description=f"Synthesize findings and analyze comparison between {', '.join(items)}.",
            agent_id="research_agent",
            action=Action(action_type="compare_findings", parameters={"items": items, "source_steps": dep_ids}),
            dependencies=dep_ids,
            parallelizable=False,
            risk_level=AgentRiskLevel.LOW,
            verification_strategy=VerificationStrategy(strategy_type="assertion", expected_state={"verified": True}),
        )

        all_steps = parallel_steps + [merge_step]

        # If user asked for a report, append report step
        if "report" in goal_lower:
            rep_id = str(uuid.uuid4())
            rep_step = TaskStep(
                id=rep_id,
                name="Generate Summary Report",
                description="Compile comparison analysis into a structured report.",
                agent_id="document_agent",
                action=Action(action_type="create_document", parameters={"title": f"{' vs '.join(items)} Report", "source": merge_id}),
                dependencies=[merge_id],
                parallelizable=False,
                risk_level=AgentRiskLevel.LOW,
                verification_strategy=VerificationStrategy(strategy_type="assertion", expected_state={"verified": True}),
            )
            all_steps.append(rep_step)

        return all_steps
