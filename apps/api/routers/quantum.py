"""Quantum Computation API Router."""

from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from packages.schemas.quantum import QuantumJob, QuantumResult
from apps.api.deps import Container, get_container

router = APIRouter(prefix="/quantum", tags=["Quantum"])

_quantum_jobs_store: Dict[str, QuantumJob] = {}


@router.post("/jobs", response_model=QuantumResult)
async def submit_quantum_job(job: QuantumJob, container: Container = Depends(get_container)):
    """Submit and execute a quantum circuit simulation or QAOA/VQE optimization."""
    _quantum_jobs_store[job.id] = job
    result = await container.quantum_engine.execute_job(job)
    return result


@router.get("/jobs/{job_id}", response_model=QuantumJob)
async def get_quantum_job(job_id: str):
    """Retrieve status and results of a submitted quantum job."""
    job = _quantum_jobs_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Quantum job not found")
    return job
