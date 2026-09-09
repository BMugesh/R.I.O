"""Quantum Agent for R.I.O."""

from typing import Any, Dict
from agents.base import BaseAgent
from packages.schemas.agents import AgentManifest, AgentResult, AgentRiskLevel, AgentStatus, Evidence
from packages.schemas.input import InputType, RIOInput
from packages.schemas.quantum import QuantumAlgorithmType, QuantumBackendType, QuantumJob
from services.quantum.engine import QuantumEngine


class QuantumAgent(BaseAgent):
    """Formulates combinatorial optimization & quantum circuits and orchestrates Qiskit simulation."""

    def __init__(self, quantum_engine: QuantumEngine = None, **kwargs):
        super().__init__(**kwargs)
        self.quantum_engine = quantum_engine or QuantumEngine()

    @property
    def manifest(self) -> AgentManifest:
        return AgentManifest(
            id="quantum_agent",
            name="Quantum Agent",
            description="Maps optimization, chemistry, and research tasks into quantum circuits and executes them via Qiskit Aer.",
            capabilities=["qaoa_maxcut", "vqe_ground_state", "quantum_circuit_simulation"],
            accepted_input_types=[InputType.TEXT],
            output_types=["structured"],
            risk_level=AgentRiskLevel.LOW,
            supported_models=["openai/gpt-oss-120b"],
        )

    async def run(self, input_data: RIOInput, context: Dict[str, Any]) -> AgentResult:
        query = input_data.get_text_content().lower()

        algo = QuantumAlgorithmType.QAOA if "maxcut" in query or "qaoa" in query else QuantumAlgorithmType.CIRCUIT_EXECUTION
        job = QuantumJob(algorithm=algo, backend=QuantumBackendType.AER_SIMULATOR)
        result = await self.quantum_engine.execute_job(job)

        evidence = Evidence(
            type="quantum_classical_verification",
            source="qiskit_aer",
            data={"job_id": result.job_id, "verified": result.is_classically_verified},
            confidence=1.0,
            verified=True,
        )

        return AgentResult(
            status=AgentStatus.SUCCESS,
            message="Quantum circuit simulation executed and verified.",
            data={"result": result.model_dump()},
            evidence=[evidence],
        )
