"""Redis & In-Memory Cache Store for R.I.O. Working State & Sessions."""

import json
import os
from typing import Any, Dict, Optional

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None


class CacheStore:
    """Hot Cache & Session State Store."""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis_client: Optional[aioredis.Redis] = None
        self._redis_failed: bool = (os.getenv("RIO_ENV") == "test")
        self._local_cache: Dict[str, Any] = {}

    async def _get_client(self):
        if aioredis is None or self._redis_failed:
            return None
        if self._redis_client is None:
            try:
                self._redis_client = aioredis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=0.2,
                )
                await self._redis_client.ping()
            except Exception:
                self._redis_failed = True
                self._redis_client = None
        return self._redis_client

    async def get(self, key: str) -> Optional[Any]:
        client = await self._get_client()
        if client:
            try:
                val = await client.get(key)
                return json.loads(val) if val else None
            except Exception:
                pass
        return self._local_cache.get(key)

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        client = await self._get_client()
        if client:
            try:
                serialized = json.dumps(value)
                if ttl_seconds:
                    await client.setex(key, ttl_seconds, serialized)
                else:
                    await client.set(key, serialized)
                return
            except Exception:
                pass
        self._local_cache[key] = value

    async def delete(self, key: str) -> bool:
        client = await self._get_client()
        if client:
            try:
                await client.delete(key)
            except Exception:
                pass
        return self._local_cache.pop(key, None) is not None
