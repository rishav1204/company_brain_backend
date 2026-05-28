from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt

from app.core.config import settings


def issue_access_token(
    *,
    user_id: str,
    org_id: str,
    roles: list[str],
    permissions: list[str],
    session_id: str,
    attrs: dict | None = None,
    email: str | None = None,
) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    ttl = settings.iam_access_token_ttl_seconds
    exp = now + timedelta(seconds=ttl)
    payload = {
        settings.jwt_tenant_claim: org_id,
        settings.jwt_user_claim: user_id,
        settings.jwt_roles_claim: roles,
        "permissions": permissions,
        "session_id": session_id,
        "email": email,
        "attrs": attrs or {},
        "jti": str(uuid4()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, ttl


def decode_session_id(token_payload: dict) -> str | None:
    session_id = token_payload.get("session_id")
    return str(session_id) if session_id else None
