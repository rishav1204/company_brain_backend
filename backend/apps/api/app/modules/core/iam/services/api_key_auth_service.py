import hashlib
from datetime import datetime, timezone

from app.modules.core.iam.repositories.api_key_repository import ApiKeyRepository

_api_key_repo = ApiKeyRepository()


def _hash_key(raw: str) -> str:
    from app.core.config import settings

    material = f"{settings.api_key_pepper}:{raw}" if settings.api_key_pepper else raw
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def authenticate_api_key(raw_key: str) -> dict | None:
    if not raw_key.startswith("cb_"):
        return None
    row = _api_key_repo.get_by_hash(_hash_key(raw_key))
    if not row or row.get("revoked"):
        return None
    expires_at = row.get("expires_at")
    if expires_at and expires_at < datetime.now(timezone.utc):
        return None
    scopes = row.get("scopes") or []
    if not isinstance(scopes, list):
        scopes = []
    return {
        "org_id": row["org_id"],
        "api_key_id": row["id"],
        "name": row["name"],
        "scopes": [str(s) for s in scopes],
        "user_id": f"apikey:{row['id']}",
        "roles": ["api_integration"],
    }


def scope_allows(scopes: list[str], required: str) -> bool:
    if not required:
        return True
    scope_set = set(scopes)
    if "*" in scope_set or "admin" in scope_set:
        return True
    return required in scope_set
