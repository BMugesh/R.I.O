"""Quantum Computation Schemas for R.I.O.

Defines schemas for quantum algorithm execution, Qiskit jobs, and classical verification.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class QuantumAlgorithmType(str, Enum):
    QAOA = "qaoa"
    VQE = "vqe"
    MAX_CUT = "max_cut"
    PORTFOLIO_OPTIMIZATION = "portfolio_optimization"
    QML_CLASSIFICATION = "qml_classification"
    CIRCUIT_EXECUTION = "circuit_execution"
    GROVER_SEARCH = "grover_search"


class QuantumBackendType(str, Enum):
    AER_SIMULATOR = "aer_simulator"
    STATEVECTOR_SIMULATOR = "statevector_simulator"
    IBM_QUANTUM = "ibm_quantum"
    MOCK_QUANTUM = "mock_quantum"


class QuantumCircuitSpec(BaseModel):
    """Specification of a quantum circuit or high-level algorithm configuration."""
    num_qubits: int = 2
    num_clbits: int = 2
    gates: List[Dict[str, Any]] = Field(default_factory=list)  # [{'gate': 'h', 'qubits': [0]}, {'gate': 'cx', 'qubits': [0, 1]}]
    parameters: Dict[str, Any] = Field(default_factory=dict)
    shots: int = 1024


class QuantumResult(BaseModel):
    """Result of a quantum computation."""
    job_id: str
    algorithm: QuantumAlgorithmType
    backend: QuantumBackendType
    counts: Dict[str, int] = Field(default_factory=dict)
    statevector: Optional[List[complex]] = None
    expectation_value: Optional[float] = None
    optimal_parameters: Optional[List[float]] = None
    optimal_value: Optional[float] = None
    execution_time_ms: float = 0.0
    classical_comparison: Optional[Dict[str, Any]] = None
    is_classically_verified: bool = False


class QuantumJob(BaseModel):
    """A quantum execution job submitted to R.I.O."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    algorithm: QuantumAlgorithmType = QuantumAlgorithmType.CIRCUIT_EXECUTION
    backend: QuantumBackendType = QuantumBackendType.AER_SIMULATOR
    circuit_spec: Optional[QuantumCircuitSpec] = None
    problem_matrix: Optional[List[List[float]]] = None  # Graph adjacency or cost matrix for QAOA/MaxCut
    status: str = "pending"  # 'pending', 'running', 'completed', 'failed'
    result: Optional[QuantumResult] = None
    error: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
