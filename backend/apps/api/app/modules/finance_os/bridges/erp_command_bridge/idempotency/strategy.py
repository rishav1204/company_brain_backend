"""Idempotency for bridge commands — reuses platform.idempotency_keys when available."""

from __future__ import annotations

import hashlib
import json
from typing import Any


_SCOPE = "erp_command_bridge"


def request_hash(material: dict[str, Any]) -> str:
    blob = json.dumps(material, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def check_idempotent(org_id: str, idempotency_key: str | None, material: dict[str, Any]) -> dict | None:
    """Return cached response dict if this key was already processed."""
    if not idempotency_key:
        return None
    try:
        from app.modules.platform.events.services.idempotency_service import platform_idempotency_service

        cached = platform_idempotency_service.get_cached(org_id, _SCOPE, idempotency_key)
        if cached:
            return cached if isinstance(cached, dict) else {"result": cached, "from_cache": True}
        # record pending intent hash via check_and_store empty then store later
        return None
    except Exception:
        return None


def store_idempotent(
    org_id: str,
    idempotency_key: str | None,
    material: dict[str, Any],
    response: dict[str, Any],
) -> None:
    if not idempotency_key:
        return
    try:
        from app.modules.platform.events.services.idempotency_service import platform_idempotency_service

        platform_idempotency_service.store(
            org_id,
            _SCOPE,
            idempotency_key,
            request_payload=material,
            response_payload=response,
        )
    except Exception:
        # Schema may be unavailable in unit tests
        pass
