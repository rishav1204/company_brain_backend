from __future__ import annotations


def fail_closed_in_prod(exc: Exception, *, operation: str) -> None:
    """In production, connector HTTP failures must not silently fall back to stubs."""
    from app.core.config import settings

    if settings.app_env.lower() == "prod":
        raise RuntimeError(f"Connector operation failed in production: {operation}") from exc
