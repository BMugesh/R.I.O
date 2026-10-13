"""Unit tests for Quantum Router, QAOA, VQE, and Simulation Engine."""
import pytest
pytestmark = pytest.mark.unit



import pytest
from packages.schemas.quantum import QuantumAlgorithmType, QuantumJob
from services.quantum.engine import QuantumEngine
from services.quantum.router import QuantumRouter


def test_quantum_suitability_router():
    is_q, algo = QuantumRouter.check_suitability("Solve maxcut problem on this graph with QAOA")
    assert is_q is True
    assert algo == QuantumAlgorithmType.QAOA

    is_q2, _ = QuantumRouter.check_suitability("What is the capital of France?")
    assert is_q2 is False


@pytest.mark.asyncio
async def test_qaoa_maxcut_execution_and_classical_verification():
    engine = QuantumEngine()
    job = QuantumJob(
        algorithm=QuantumAlgorithmType.QAOA,
        problem_matrix=[[0, 1, 1], [1, 0, 1], [1, 1, 0]],
    )
    result = await engine.execute_job(job)

    assert result.job_id == job.id
    assert result.is_classically_verified is True
    assert result.optimal_value is not None
    assert "classical_optimal" in result.classical_comparison
