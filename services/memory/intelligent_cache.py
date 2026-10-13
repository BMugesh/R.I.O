"""Intelligent Cache Manager for R.I.O. (Milestone 5).

Provides policy-gated caching, cache-aside abstractions, TTL freshness validation,
and telemetry tracking.
"""

import logging
import time
from typing import Any, Dict, Optional

from services.memory.cache_policy import CacheEntry, CachePolicyEngine, CacheTier

logger = logging.getLogger("rio.memory.intelligent_cache")


class IntelligentCacheManager:
    """Policy-aware cache manager with telemetry and automated freshness gating."""

    def __init__(self):
        self._entries: Dict[str, CacheEntry] = {}
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0

    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache if admitted and not expired."""
        entry = self._entries.get(key)
        if entry is None:
            self._misses += 1
            return None

        # Check expiration
        if entry.is_expired():
            logger.debug(f"Cache entry for '{key}' expired. Evicting.")
            del self._entries[key]
            self._evictions += 1
            self._misses += 1
            return None

        self._hits += 1
        return entry.value

    def get_entry(self, key: str) -> Optional[CacheEntry]:
        """Retrieve full CacheEntry metadata envelope."""
        entry = self._entries.get(key)
        if entry and not entry.is_expired():
            return entry
        return None

    def set(
        self,
        key: str,
        value: Any,
        tier: CacheTier = CacheTier.SHORT_LIVED,
        is_verified: bool = True,
        is_sensitive: bool = False,
        source: str = "local",
        confidence: float = 1.0,
        custom_ttl: Optional[int] = None,
    ) -> bool:
        """Admit value to cache if allowed by policy."""
        # 1. Policy admission check
        if not CachePolicyEngine.can_admit(value, tier=tier, is_verified=is_verified, is_sensitive=is_sensitive):
            logger.warning(f"Cache admission denied for key='{key}' (tier={tier}, is_verified={is_verified}, is_sensitive={is_sensitive})")
            return False

        # 2. Expiration calculation
        expires_at = CachePolicyEngine.compute_expiration(tier=tier, custom_ttl=custom_ttl)

        entry = CacheEntry(
            key=key,
            value=value,
            tier=tier,
            created_at=time.time(),
            expires_at=expires_at,
            source=source,
            confidence=confidence,
            is_verified=is_verified,
            is_sensitive=is_sensitive,
        )
        self._entries[key] = entry
        return True

    def delete(self, key: str) -> bool:
        """Remove entry from cache."""
        return self._entries.pop(key, None) is not None

    def invalidate_tier(self, tier: CacheTier) -> int:
        """Invalidate all cached entries belonging to a specific tier."""
        keys_to_del = [k for k, v in self._entries.items() if v.tier == tier]
        for k in keys_to_del:
            del self._entries[k]
        self._evictions += len(keys_to_del)
        return len(keys_to_del)

    def get_metrics(self) -> Dict[str, Any]:
        """Return cache telemetry metrics."""
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests) if total_requests > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "evictions": self._evictions,
            "total_active_entries": len(self._entries),
        }
