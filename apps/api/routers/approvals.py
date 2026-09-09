"""Approvals API Router."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from packages.schemas.safety import ApprovalDecision, ApprovalRequest, ApprovalStatus
from apps.api.deps import Container, get_container

router = APIRouter(prefix="/approvals", tags=["Approvals"])


@router.get("", response_model=List[ApprovalRequest])
async def list_pending_approvals(task_id: Optional[str] = None, container: Container = Depends(get_container)):
    """List pending approval requests."""
    return container.approval_engine.get_pending(task_id=task_id)


@router.post("/{request_id}")
async def submit_approval_decision(request_id: str, decision: ApprovalDecision, container: Container = Depends(get_container)):
    """Submit user approval or denial for a high-risk operation."""
    decision.request_id = request_id
    success = container.approval_engine.resolve_decision(decision)
    if not success:
        raise HTTPException(status_code=404, detail="Approval request not found or already resolved")
    return {"status": "resolved", "decision": decision.decision.value}
