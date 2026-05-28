from __future__ import annotations

from hashlib import sha256

from app.modules.platform.integrations.repositories.api_key_repository import api_key_repository


def authenticate_integration_api_key(raw_key: str) -> dict | None:
    """
    Authenticate Module 7 API keys (prefix `cbk_`).
    """
    if not raw_key or not raw_key.startswith("cbk_"):
        return None
    key_hash = sha256(raw_key.encode()).hexdigest()
    row = api_key_repository.get_by_hash(key_hash)
    if not row:
        return None
    try:
        api_key_repository.mark_used(api_key_id=str(row["id"]))
    except Exception:
        pass
    return {
        "api_key_id": row["id"],
        "org_id": row["org_id"],
        "user_id": "integrations_api_key",
        "roles": ["system_worker"],
        "scopes": row.get("scopes") or [],
    }

