"""Approval Engine for R.I.O.

Manages human-in-the-loop approval queues, timeouts, and decision resolution.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from packages.schemas.agents import AgentRiskLevel
from packages.schemas.safety import ApprovalDecision, ApprovalRequest, ApprovalStatus


class ApprovalEngine:
    """Manages pending and resolved human approvals."""

    def __init__(self):
        self._pending_requests: Dict[str, ApprovalRequest] = {}
        self._futures: Dict[str, asyncio.Future] = {}
        self._resolved_requests: Dict[str, ApprovalRequest] = {}

    def create_request(
        self,
        task_id: str,
        action_type: str,
        description: str,
        risk_level: AgentRiskLevel,
        parameters: Optional[Dict[str, Any]] = None,
        step_id: Optional[str] = None,
        target: Optional[str] = None,
    ) -> ApprovalRequest:
        """Create a new pending approval request."""
        req = ApprovalRequest(
            task_id=task_id,
            step_id=step_id,
            action_type=action_type,
            target=target,
            description=description,
            parameters=parameters or {},
            risk_level=risk_level,
            status=ApprovalStatus.PENDING,
        )
        self._pending_requests[req.id] = req
        loop = asyncio.get_event_loop()
        self._futures[req.id] = loop.create_future()
        return req

    async def wait_for_decision(self, request_id: str, timeout_seconds: float = 300.0) -> ApprovalStatus:
        """Asynchronously wait until the user approves or denies the request."""
        if request_id in self._resolved_requests:
            return self._resolved_requests[request_id].status

        future = self._futures.get(request_id)
        if not future:
            return ApprovalStatus.DENIED

        try:
            decision = await asyncio.wait_for(future, timeout=timeout_seconds)
            return decision
        except asyncio.TimeoutError:
            self.resolve_decision(ApprovalDecision(request_id=request_id, decision=ApprovalStatus.EXPIRED, reason="Timeout waiting for user approval"))
            return ApprovalStatus.EXPIRED

    def resolve_decision(self, decision: ApprovalDecision) -> bool:
        """Submit user decision to resolve a pending request."""
        req = self._pending_requests.pop(decision.request_id, None)
        if not req:
            return False

        req.status = decision.decision
        req.resolved_at = datetime.now(timezone.utc).isoformat()
        req.resolved_by = decision.user_id or "user"
        req.decision_reason = decision.reason
        self._resolved_requests[req.id] = req

        future = self._futures.pop(decision.request_id, None)
        if future and not future.done():
            future.set_result(decision.decision)
        return True

    def get_pending(self, task_id: Optional[str] = None) -> List[ApprovalRequest]:
        """List all pending approval requests."""
        if task_id:
            return [r for r in self._pending_requests.values() if r.task_id == task_id]
        return list(self._pending_requests.values())

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get approval request by ID."""
        return self._pending_requests.get(request_id) or self._resolved_requests.get(request_id)
