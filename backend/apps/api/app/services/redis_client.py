"""Shared Redis connection pool for application services."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from redis import ConnectionPool, Redis

_pool: ConnectionPool | None = None


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
    pool = get_redis_pool()
    if pool is None:
        return None
    from redis import Redis

    return Redis(connection_pool=pool)


def close_redis_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.disconnect()
        _pool = None
