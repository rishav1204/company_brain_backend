"""WebAuthn / passkey enrollment and authentication."""

from __future__ import annotations

import json
import secrets

from app.core.config import settings
from app.modules.core.iam.repositories.mfa_repository import mfa_repo
from app.services.redis_client import get_redis_client

_CHALLENGE_PREFIX = "iam:webauthn"
_CHALLENGE_TTL = 300


def _redis():
    return get_redis_client()


def begin_registration(org_id: str, user_id: str, email: str) -> dict:
    challenge = secrets.token_urlsafe(32)
    _redis().setex(f"{_CHALLENGE_PREFIX}:reg:{user_id}", _CHALLENGE_TTL, challenge)
    return {
        "challenge": challenge,
        "rp": {"id": settings.webauthn_rp_id, "name": settings.webauthn_rp_name},
        "user": {"id": user_id, "name": email, "displayName": email},
        "pubKeyCredParams": [{"type": "public-key", "alg": -7}, {"type": "public-key", "alg": -257}],
        "timeout": 60000,
        "attestation": "none",
    }


def finish_registration(org_id: str, user_id: str, credential: dict) -> None:
    stored = _redis().get(f"{_CHALLENGE_PREFIX}:reg:{user_id}")
    if not stored:
        raise ValueError("Registration challenge expired")
    _redis().delete(f"{_CHALLENGE_PREFIX}:reg:{user_id}")
    cred_id = str(credential.get("id") or credential.get("credential_id") or "")
    if not cred_id:
        raise ValueError("Missing credential id")
    mfa_repo.upsert_method(
        org_id,
        user_id,
        "webauthn",
        enabled=True,
        metadata={"credentials": [credential], "credential_id": cred_id},
    )


def begin_authentication(org_id: str, user_id: str) -> dict:
    method = mfa_repo.get_method(org_id, user_id, "webauthn")
    if not method or not method.get("enabled"):
        raise ValueError("WebAuthn not enrolled")
    challenge = secrets.token_urlsafe(32)
    _redis().setex(f"{_CHALLENGE_PREFIX}:auth:{user_id}", _CHALLENGE_TTL, challenge)
    meta = method.get("metadata") or {}
    if isinstance(meta, str):
        meta = json.loads(meta)
    cred_id = meta.get("credential_id")
    return {
        "challenge": challenge,
        "timeout": 60000,
        "allowCredentials": [{"type": "public-key", "id": cred_id}] if cred_id else [],
    }


def finish_authentication(org_id: str, user_id: str, assertion: dict) -> bool:
    stored = _redis().get(f"{_CHALLENGE_PREFIX}:auth:{user_id}")
    if not stored:
        return False
    _redis().delete(f"{_CHALLENGE_PREFIX}:auth:{user_id}")
    method = mfa_repo.get_method(org_id, user_id, "webauthn")
    if not method or not method.get("enabled"):
        return False
    meta = method.get("metadata") or {}
    if isinstance(meta, str):
        meta = json.loads(meta)
    expected_id = meta.get("credential_id")
    return bool(expected_id and str(assertion.get("id") or "") == str(expected_id))
