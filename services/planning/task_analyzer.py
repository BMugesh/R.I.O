"""Task Analyzer for R.I.O. (Milestone 5).

Deep structural and resource analysis of user intent before planning.
Evaluates goal complexity, risk, resource requirements, capabilities,
and verification needs.
"""

import re
from typing import Any, Dict, List, Optional
import uuid

from services.planning.plan_models import TaskAnalysis


class TaskAnalyzer:
    """Analyzes a task goal to determine structural, resource, and risk requirements."""

    DESTRUCTIVE_PATTERNS = [
        r"\bdelete\b",
        r"\bremove\b",
        r"\bkill\b",
        r"\bformat\b",
        r"\bdrop\b",
        r"\bpurchase\b",
        r"\bbuy\b",
        r"\btransfer\b",
        r"\bshutdown\b",
    ]

    GPU_PATTERNS = [
        r"\bvision\b",
        r"\bimage\b",
        r"\bscreenshot\b",
        r"\bvisual\b",
        r"\btranscribe\b",
        r"\bspeech\b",
        r"\baudio\b",
        r"\bembedding\b",
        r"\brerank\b",
    ]

    NETWORK_PATTERNS = [
        r"\bresearch\b",
        r"\bsearch\b",
        r"\bweb\b",
        r"\bbrowse\b",
        r"\bchrome\b",
        r"\bdownload\b",
        r"\bapi\b",
        r"\bhttp\b",
        r"\burl\b",
    ]

    DEVICE_PATTERNS = [
        r"\bphone\b",
        r"\bandroid\b",
        r"\blaptop\b",
        r"\bmobile\b",
        r"\bwhatsapp\b",
        r"\bdevice\b",
    ]

    def analyze(self, goal: str, context: Optional[Dict[str, Any]] = None) -> TaskAnalysis:
        """Analyze a goal and output a structured TaskAnalysis."""
        goal_lower = goal.lower()
        task_id = str(uuid.uuid4())

        # 1. Determine capabilities
        caps: List[str] = []
        if any(re.search(p, goal_lower) for p in self.GPU_PATTERNS):
            caps.append("gpu_compute")
        if any(re.search(p, goal_lower) for p in self.NETWORK_PATTERNS):
            caps.append("network_access")
        if any(re.search(p, goal_lower) for p in self.DEVICE_PATTERNS):
            caps.append("device_control")
        if "code" in goal_lower or "python" in goal_lower or "script" in goal_lower:
            caps.append("code_execution")
        if "quantum" in goal_lower or "qaoa" in goal_lower or "circuit" in goal_lower:
            caps.append("quantum_simulation")
        if not caps:
            caps.append("general_reasoning")

        # 2. Risk & Reversibility Analysis
        is_destructive = any(re.search(p, goal_lower) for p in self.DESTRUCTIVE_PATTERNS)
        if is_destructive:
            risk_level = "critical"
            reversible = False
            requires_approval = True
            verification_level = "critical"
        elif "send" in goal_lower or "install" in goal_lower or "write" in goal_lower:
            risk_level = "medium"
            reversible = False
            requires_approval = False
            verification_level = "standard"
        else:
            risk_level = "low"
            reversible = True
            requires_approval = False
            verification_level = "basic" if len(goal.split()) <= 4 else "standard"

        # 3. Complexity Analysis
        # Count distinct operational clauses/connectors (e.g. "and", "then", "compare", commas)
        clauses = re.split(r"\b(?:and|then|also|after that)\b|,", goal_lower)
        clauses = [c.strip() for c in clauses if c.strip()]
        if len(clauses) >= 4 or "compare" in goal_lower or "benchmark" in goal_lower:
            complexity = "high"
        elif len(clauses) >= 2:
            complexity = "medium"
        else:
            complexity = "low"

        # 4. Resource Estimations
        requires_gpu = "gpu_compute" in caps
        requires_network = "network_access" in caps or "device_control" in caps
        requires_device = "device_control" in caps

        estimated_duration_ms = 1000
        if complexity == "high":
            estimated_duration_ms = 5000
        elif complexity == "medium":
            estimated_duration_ms = 2500

        estimated_memory_mb = 250
        if requires_network:
            estimated_memory_mb += 150
        if requires_gpu:
            estimated_memory_mb += 200

        estimated_vram_mb = 1200 if requires_gpu else 0

        return TaskAnalysis(
            task_id=task_id,
            goal=goal,
            complexity=complexity,
            risk_level=risk_level,
            required_capabilities=caps,
            estimated_duration_ms=estimated_duration_ms,
            estimated_memory_mb=estimated_memory_mb,
            estimated_vram_mb=estimated_vram_mb,
            requires_network=requires_network,
            requires_gpu=requires_gpu,
            requires_device=requires_device,
            reversible=reversible,
            requires_approval=requires_approval,
            verification_level=verification_level,
            metadata={"clause_count": len(clauses)},
        )
