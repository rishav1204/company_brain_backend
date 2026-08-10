from __future__ import annotations

import secrets
from hashlib import sha256

from app.modules.platform.integrations.repositories.api_key_repository import api_key_repository

_FORBIDDEN_SCOPES = frozenset({"*", "admin"})


class ApiKeyService:
    def _hash(self, raw_key: str) -> str:
        return sha256(raw_key.encode()).hexdigest()

    def _validate_scopes(self, scopes: list[str]) -> None:
        for scope in scopes or []:
            if scope in _FORBIDDEN_SCOPES:
                raise ValueError(f"Wildcard scope '{scope}' is not allowed on integration API keys")

    def create(self, org_id: str, *, name: str, scopes: list[str]) -> tuple[dict, str]:
        self._validate_scopes(scopes)
        raw_key = "cbk_" + secrets.token_urlsafe(32)
        key_hash = self._hash(raw_key)
        item = api_key_repository.create(org_id, name=name, key_hash=key_hash, scopes=scopes or [])
        return item, raw_key

    def list(self, org_id: str) -> list[dict]:
        return api_key_repository.list(org_id)

    def revoke(self, org_id: str, *, api_key_id: str) -> dict:
        return api_key_repository.revoke(org_id, api_key_id=api_key_id)

    def rotate(self, org_id: str, *, api_key_id: str) -> tuple[dict, str]:
        # Rotate == revoke old and create new with same scopes/name best-effort.
        keys = api_key_repository.list(org_id)
        old = next((k for k in keys if str(k.get("id")) == api_key_id), None)
        if not old:
            raise ValueError("api_key_not_found")
        self.revoke(org_id, api_key_id=api_key_id)
        return self.create(org_id, name=str(old.get("name") or "rotated-key"), scopes=list(old.get("scopes") or []))


api_key_service = ApiKeyService()

