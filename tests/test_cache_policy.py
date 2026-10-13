"""Unit tests for R.I.O. M5.4 Intelligent Caching."""

import time
import pytest
pytestmark = [pytest.mark.unit]

from services.memory.cache_policy import CachePolicyEngine, CacheTier
from services.memory.intelligent_cache import IntelligentCacheManager


def test_cache_admission_rejection_for_sensitive_data():
    cache = IntelligentCacheManager()

    admitted = cache.set("user_pwd", "secret123", is_sensitive=True)
    assert admitted is False
    assert cache.get("user_pwd") is None


def test_cache_admission_rejection_for_unverified_tool_result():
    cache = IntelligentCacheManager()

    # Unverified tool result must NOT be admitted as authoritative fact
    admitted = cache.set("tool_weather", {"temp": 25}, tier=CacheTier.TOOL_RESULT, is_verified=False)
    assert admitted is False
    assert cache.get("tool_weather") is None


def test_cache_ttl_expiration():
    cache = IntelligentCacheManager()

    # Set item with 0.1s TTL
    cache.set("quick_key", "quick_value", tier=CacheTier.DEVICE_STATE, custom_ttl=0)
    # Since custom_ttl is 0, expires_at <= time.time()
    time.sleep(0.01)

    val = cache.get("quick_key")
    assert val is None
    metrics = cache.get_metrics()
    assert metrics["evictions"] >= 1


def test_cache_hit_rate_telemetry():
    cache = IntelligentCacheManager()

    cache.set("item1", "val1", tier=CacheTier.STATIC)

    # 1 hit
    assert cache.get("item1") == "val1"
    # 2 misses
    assert cache.get("item2") is None
    assert cache.get("item3") is None

    metrics = cache.get_metrics()
    assert metrics["hits"] == 1
    assert metrics["misses"] == 2
    assert abs(metrics["hit_rate"] - (1.0 / 3.0)) < 1e-4


def test_cache_tier_invalidation():
    cache = IntelligentCacheManager()

    cache.set("s1", "v1", tier=CacheTier.SHORT_LIVED)
    cache.set("s2", "v2", tier=CacheTier.SHORT_LIVED)
    cache.set("m1", "v3", tier=CacheTier.MEMORY)

    assert cache.get("s1") == "v1"
    count = cache.invalidate_tier(CacheTier.SHORT_LIVED)
    assert count == 2

    assert cache.get("s1") is None
    assert cache.get("s2") is None
    assert cache.get("m1") == "v3"
