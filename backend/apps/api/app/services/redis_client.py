"""Shared Redis connection pool and singleton client for application services."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from redis import ConnectionPool, Redis

_pool: ConnectionPool | None = None
_client: Redis | None = None
_client_ready: bool = False


def get_redis_pool() -> ConnectionPool | None:
    global _pool
    redis_url = (settings.redis_url or "").strip()
    if not redis_url:
        return None
    if settings.redis_require_tls and not redis_url.lower().startswith("rediss://"):
        raise RuntimeError("REDIS_REQUIRE_TLS=true requires REDIS_URL to use rediss://")
    if _pool is None:
        from redis import ConnectionPool

        _pool = ConnectionPool.from_url(
            redis_url,
            max_connections=settings.redis_pool_max_connections,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=10,
        )
    return _pool


def get_redis_client() -> Redis | None:
    """Return a process-wide Redis client backed by the shared connection pool."""
    global _client, _client_ready
    if _client_ready:
        return _client
    pool = get_redis_pool()
    if pool is None:
        _client_ready = True
        _client = None
        return None
    from redis import Redis

    _client = Redis(connection_pool=pool)
    _client_ready = True
    return _client


def close_redis_pool() -> None:
    global _pool, _client, _client_ready
    if _pool is not None:
        _pool.disconnect()
    _pool = None
    _client = None
    _client_ready = False
