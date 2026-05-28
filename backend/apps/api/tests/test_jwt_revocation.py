from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError

from app.core.config import settings
from app.services import jwt_auth


def _build_token_with_jti(jti: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        settings.jwt_tenant_claim: "org-demo",
        settings.jwt_user_claim: "user-demo",
        settings.jwt_roles_claim: ["tenant_admin"],
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "jti": jti,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def test_decode_rejects_revoked_jti(monkeypatch) -> None:
    token = _build_token_with_jti("revoked-jti-1")
    monkeypatch.setattr(jwt_auth, "_is_token_revoked", lambda jti: jti == "revoked-jti-1")
    try:
        jwt_auth.decode_bearer_token(token)
        assert False, "Expected revoked token rejection"
    except InvalidTokenError as exc:
        assert "revoked" in str(exc).lower()


def test_decode_allows_non_revoked_jti(monkeypatch) -> None:
    token = _build_token_with_jti("active-jti-1")
    monkeypatch.setattr(jwt_auth, "_is_token_revoked", lambda jti: False)
    principal = jwt_auth.decode_bearer_token(token)
    assert principal.org_id == "org-demo"
