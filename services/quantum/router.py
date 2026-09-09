"""Quantum Suitability Router for R.I.O.

Determines whether a computational or optimization problem should be routed
to the Quantum Engine (Qiskit/Aer) or solved classically.
"""

from typing import Any, Dict, Optional, Tuple
from packages.schemas.quantum import QuantumAlgorithmType


class QuantumRouter:
    """Evaluates problem suitability for quantum acceleration."""

    QUANTUM_KEYWORDS = [
        "qaoa",
        "vqe",
        "quantum",
        "qubit",
        "circuit",
        "maxcut",
        "max cut",
        "hamiltonian",
        "grover",
        "ising",
        "superposition",
        "entanglement",
    ]

    @classmethod
    def check_suitability(cls, user_prompt: str, task_metadata: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[QuantumAlgorithmType]]:
        """Assess if user prompt or metadata warrants quantum processing."""
        prompt_lower = user_prompt.lower()

        # Explicit algorithm matching
        if "maxcut" in prompt_lower or "max cut" in prompt_lower or "qaoa" in prompt_lower:
            return True, QuantumAlgorithmType.QAOA
        if "vqe" in prompt_lower or "molecular energy" in prompt_lower or "ground state" in prompt_lower:
            return True, QuantumAlgorithmType.VQE
        if "grover" in prompt_lower or "quantum search" in prompt_lower:
            return True, QuantumAlgorithmType.GROVER_SEARCH
        if "quantum circuit" in prompt_lower or "bell state" in prompt_lower:
            return True, QuantumAlgorithmType.CIRCUIT_EXECUTION

        if any(kw in prompt_lower for kw in cls.QUANTUM_KEYWORDS):
            return True, QuantumAlgorithmType.CIRCUIT_EXECUTION

        return False, None
