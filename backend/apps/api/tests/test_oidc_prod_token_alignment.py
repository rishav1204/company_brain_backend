from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError

from app.core.config import settings
from app.services.oidc_service import oidc_service


def _build_hs_token(org_id: str, user_id: str, roles: list[str]) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        settings.jwt_tenant_claim: org_id,
        settings.jwt_user_claim: user_id,
        settings.jwt_roles_claim: roles,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def test_oidc_prod_mode_requires_jwks_compatible_upstream_token() -> None:
    prev_env = settings.app_env
    prev_require = settings.jwt_require_jwks_in_prod
    prev_jwks = settings.jwt_jwks_url
    settings.app_env = "prod"
    settings.jwt_require_jwks_in_prod = True
    settings.jwt_jwks_url = "https://example.invalid/jwks.json"
    try:
        claims = {"sub": "user1", "org_id": "org-demo", "roles": ["tenant_admin"]}
        try:
            oidc_service.issue_api_session(
                claims=claims,
                upstream_access_token=_build_hs_token("org-demo", "user1", ["tenant_admin"]),
            )
            assert False, "Expected prod JWT policy validation failure"
        except ValueError as exc:
            assert "not compatible" in str(exc)
    finally:
        settings.app_env = prev_env
        settings.jwt_require_jwks_in_prod = prev_require
        settings.jwt_jwks_url = prev_jwks


def test_oidc_non_prod_can_issue_local_api_session_token() -> None:
    prev_env = settings.app_env
    settings.app_env = "dev"
    try:
        claims = {"sub": "user2", "org_id": "org-demo", "roles": ["tenant_admin"], "attrs": {}}
        session = oidc_service.issue_api_session(claims=claims, include_refresh=False)
        assert "access_token" in session
        decoded = jwt.decode(
            session["access_token"],
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
        assert decoded.get(settings.jwt_user_claim) == "user2"
    except InvalidTokenError as exc:
        assert False, f"Token should be decodable in non-prod mode: {exc}"
    finally:
        settings.app_env = prev_env
