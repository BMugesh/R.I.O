"""Compute routing policy and default workload assignment for R.I.O."""

from typing import Any, Dict, Optional

from services.compute.workload import ComputeDecision, ComputeTarget, Workload

# Default Workload Placement Policy matching R.I.O. Milestone 4 architecture
DEFAULT_COMPUTE_POLICY: Dict[str, str] = {
    # GPU Accelerator Workloads (RTX 4050 6GB)
    "embedding": "GPU",
    "vision_inference": "GPU",
    "speech_to_text": "GPU_OR_REMOTE",
    "reranking": "GPU",
    "ml_inference": "GPU",

    # Remote Cloud Workloads (Groq)
    "complex_reasoning": "REMOTE",
    "planning": "REMOTE",
    "coding": "REMOTE",
    "conversation": "REMOTE",
    "web_research": "REMOTE",

    # CPU Workloads (OS Control Plane)
    "browser_control": "CPU",
    "device_control": "CPU",
    "scheduler": "CPU",
    "database": "CPU",
    "websocket": "CPU",
    "quantum_simulation": "CPU",
    "general_compute": "CPU",
}


class ComputePolicy:
    """Evaluates workloads against system policies, hardware constraints, and privacy gates."""

    def __init__(self, policy_table: Optional[Dict[str, str]] = None):
        self.policy_table = dict(DEFAULT_COMPUTE_POLICY)
        if policy_table:
            self.policy_table.update(policy_table)

    def get_preferred_target(self, workload_type: str) -> str:
        """Look up preferred placement rule for workload type."""
        return self.policy_table.get(workload_type, "CPU")

    def evaluate(
        self,
        workload: Workload,
        gpu_available: bool,
        free_vram_mb: int,
    ) -> ComputeDecision:
        """Determine target execution platform with strict safety and privacy compliance."""
        pref = self.get_preferred_target(workload.type)

        # 1. Strict Privacy Check: local_only forbids REMOTE entirely
        if workload.privacy == "local_only" and pref == "REMOTE":
            # Demote remote requirement to local CPU or GPU
            pref = "GPU" if workload.allow_gpu and gpu_available else "CPU"

        # 2. VRAM constraint check
        has_vram = free_vram_mb >= workload.estimated_memory_mb

        # 3. Decision resolution
        if pref == "GPU":
            if workload.allow_gpu and gpu_available and has_vram:
                return ComputeDecision(
                    target=ComputeTarget.GPU,
                    reason="Preferred GPU workload, CUDA available, sufficient VRAM",
                    fallback=ComputeTarget.CPU,
                )
            else:
                reason = "GPU unavailable" if not gpu_available else ("VRAM insufficient" if not has_vram else "GPU not allowed")
                return ComputeDecision(
                    target=ComputeTarget.CPU,
                    reason=f"Fell back to CPU: {reason}",
                    fallback=None,
                )

        elif pref == "GPU_OR_REMOTE":
            if workload.allow_gpu and gpu_available and has_vram:
                return ComputeDecision(
                    target=ComputeTarget.GPU,
                    reason="Dynamic GPU/Remote: selected local GPU for lower latency & offline privacy",
                    fallback=ComputeTarget.REMOTE if workload.privacy != "local_only" and workload.allow_remote else ComputeTarget.CPU,
                )
            elif workload.allow_remote and workload.privacy != "local_only":
                return ComputeDecision(
                    target=ComputeTarget.REMOTE,
                    reason="Dynamic GPU/Remote: GPU unavailable/full, offloading to remote cloud",
                    fallback=ComputeTarget.CPU,
                )
            else:
                return ComputeDecision(
                    target=ComputeTarget.CPU,
                    reason="Dynamic GPU/Remote: GPU & Remote unavailable, using CPU",
                    fallback=None,
                )

        elif pref == "REMOTE":
            if workload.privacy == "local_only":
                return ComputeDecision(
                    target=ComputeTarget.CPU,
                    reason="Privacy policy 'local_only' forbids remote routing",
                    fallback=None,
                )
            if workload.allow_remote:
                return ComputeDecision(
                    target=ComputeTarget.REMOTE,
                    reason="Preferred Remote workload (large model / web synthesis)",
                    fallback=ComputeTarget.CPU,
                )
            return ComputeDecision(
                target=ComputeTarget.CPU,
                reason="Remote not allowed for this workload",
                fallback=None,
            )

        else:  # CPU default
            return ComputeDecision(
                target=ComputeTarget.CPU,
                reason="Standard OS/Control plane workload executed on CPU",
                fallback=None,
            )
