"""Intelligent Cache Policies & Entry Metadata for R.I.O. (Milestone 5).

Defines cache tiers, expiration rules, confidence gating, and sensitivity guards.
"""

from datetime import datetime, timezone
from enum import Enum
import time
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class CacheTier(str, Enum):
    STATIC = "static"              # Hardware specs, manifests (TTL: 24h+)
    SHORT_LIVED = "short_lived"    # Web search results, tool output (TTL: 5m)
    SESSION = "session"            # Active session state (TTL: 1h)
    DEVICE_STATE = "device_state"  # Live device metrics (TTL: 30s)
    MEMORY = "memory"              # Semantic facts (TTL: 7d)
    MODEL_RESULT = "model_result"  # Deterministic completions (TTL: 1h)
    TOOL_RESULT = "tool_result"    # Verified tool observations (TTL: 10m)


TIER_DEFAULT_TTLS: Dict[CacheTier, int] = {
    CacheTier.STATIC: 86400,        # 24 hours
    CacheTier.SHORT_LIVED: 300,     # 5 minutes
    CacheTier.SESSION: 3600,        # 1 hour
    CacheTier.DEVICE_STATE: 30,     # 30 seconds
    CacheTier.MEMORY: 604800,       # 7 days
    CacheTier.MODEL_RESULT: 3600,   # 1 hour
    CacheTier.TOOL_RESULT: 600,     # 10 minutes
}


class CacheEntry(BaseModel):
    """Rich metadata envelope wrapping cached objects."""

    key: str
    value: Any
    tier: CacheTier
    created_at: float = Field(default_factory=time.time)
    expires_at: Optional[float] = None
    source: str = "local"
    version: str = "1.0"
    confidence: float = 1.0
    is_verified: bool = True
    is_sensitive: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if this entry has passed its expiration time."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class CachePolicyEngine:
    """Enforces safety, freshness, and admission rules for caching."""

    @staticmethod
    def can_admit(
        value: Any,
        tier: CacheTier,
        is_verified: bool = True,
        is_sensitive: bool = False,
    ) -> bool:
        """Evaluate if an item is allowed into cache according to R.I.O. security policies."""
        # 1. Never cache sensitive data without explicit policy bypass
        if is_sensitive:
            return False

        # 2. Never cache unverified tool results as authoritative facts
        if tier == CacheTier.TOOL_RESULT and not is_verified:
            return False

        return True

    @staticmethod
    def compute_expiration(tier: CacheTier, custom_ttl: Optional[int] = None) -> float:
        """Compute epoch timestamp when the entry should expire."""
        ttl = custom_ttl if custom_ttl is not None else TIER_DEFAULT_TTLS.get(tier, 300)
        return time.time() + ttl
