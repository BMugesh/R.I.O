"""Ephemeral in-memory session store with strict 30-minute TTL and bounded capacity."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from fastapi import HTTPException, status

from schemas import (
    CalibrationDimensions,
    EvidenceRecord,
    ExecutionEvent,
    ExecutionPlan,
    PendingApproval,
    SessionStatus,
    SimulatedArtifact,
)
from security import get_max_active_sessions, get_session_ttl_seconds


@dataclass
class SessionRecord:
    session_id: str
    status: SessionStatus
    task: str
    scenario_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    plan: ExecutionPlan
    calibration_dimensions: CalibrationDimensions
    interaction_count: int = 0
    event_seq_counter: int = 0
    paused_from_status: Optional[SessionStatus] = None
    pending_approval: Optional[PendingApproval] = None
    events: List[ExecutionEvent] = field(default_factory=list)
    evidence: List[EvidenceRecord] = field(default_factory=list)
    what_rio_did: List[str] = field(default_factory=list)
    why_decisions_made: List[str] = field(default_factory=list)
    uncertainty_notes: List[str] = field(default_factory=list)
    simulated_artifact: Optional[SimulatedArtifact] = None
    calibration_label: str = "policy_enforced_unvalidated_output"
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    runner_task: Optional[asyncio.Task] = None


class InMemorySessionStore:
    """Thread/async-safe ephemeral in-memory store for isolated demo sessions."""

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionRecord] = {}

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def purge_expired(self) -> int:
        now = self._now()
        expired_ids = [
            sid for sid, rec in self._sessions.items() if now >= rec.expires_at
        ]
        for sid in expired_ids:
            rec = self._sessions.pop(sid, None)
            if rec and rec.runner_task and not rec.runner_task.done():
                rec.runner_task.cancel()
        return len(expired_ids)

    def create(self, record: SessionRecord) -> SessionRecord:
        self.purge_expired()
        max_sessions = get_max_active_sessions()
        if len(self._sessions) >= max_sessions:
            terminal_states = {
                SessionStatus.COMPLETED,
                SessionStatus.REJECTED,
                SessionStatus.CANCELLED,
            }
            candidates = sorted(
                self._sessions.values(),
                key=lambda r: (0 if r.status in terminal_states else 1, r.updated_at),
            )
            if candidates:
                victim = candidates[0]
                if victim.runner_task and not victim.runner_task.done():
                    victim.runner_task.cancel()
                self._sessions.pop(victim.session_id, None)

        self._sessions[record.session_id] = record
        return record

    def get(self, session_id: str) -> SessionRecord:
        rec = self._sessions.get(session_id)
        if rec is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Demo session not found or has already been purged.",
            )
        if self._now() >= rec.expires_at:
            if rec.runner_task and not rec.runner_task.done():
                rec.runner_task.cancel()
            self._sessions.pop(session_id, None)
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Demo session expired after the configured TTL. Please start a new session.",
            )
        return rec

    def new_timestamps(self) -> tuple[datetime, datetime]:
        now = self._now()
        ttl = get_session_ttl_seconds()
        return now, now + timedelta(seconds=ttl)

    def ttl_remaining(self, record: SessionRecord) -> int:
        remaining = int((record.expires_at - self._now()).total_seconds())
        return max(0, remaining)

    def count(self) -> int:
        self.purge_expired()
        return len(self._sessions)

    def clear(self) -> None:
        for rec in self._sessions.values():
            if rec.runner_task and not rec.runner_task.done():
                rec.runner_task.cancel()
        self._sessions.clear()


session_store = InMemorySessionStore()
