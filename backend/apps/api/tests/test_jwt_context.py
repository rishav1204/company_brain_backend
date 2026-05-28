import jwt
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


client = TestClient(app)


def build_token(org_id: str, user_id: str, roles: list[str]) -> str:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    payload = {
        settings.jwt_tenant_claim: org_id,
        settings.jwt_user_claim: user_id,
        settings.jwt_roles_claim: roles,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def test_bearer_token_context() -> None:
    token = build_token("org-demo", "user-jwt", ["tenant_admin"])
    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["org_id"] == "org-demo"
    assert body["user_id"] == "user-jwt"


def test_invalid_bearer_token_rejected() -> None:
    response = client.get("/api/v1/me", headers={"Authorization": "Bearer bad-token"})
    assert response.status_code == 401


def test_prod_requires_jwks_configuration() -> None:
    prev_env = settings.app_env
    prev_require = settings.jwt_require_jwks_in_prod
    prev_jwks = settings.jwt_jwks_url
    settings.app_env = "prod"
    settings.jwt_require_jwks_in_prod = True
    settings.jwt_jwks_url = ""
    try:
        token = build_token("org-demo", "user-jwt", ["tenant_admin"])
        response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        assert "JWT_JWKS_URL" in response.json().get("detail", "")
    finally:
        settings.app_env = prev_env
        settings.jwt_require_jwks_in_prod = prev_require
        settings.jwt_jwks_url = prev_jwks
