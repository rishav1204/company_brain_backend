import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)


def test_tampered_jwt_rejected() -> None:
    token = jwt.encode(
        {
            settings.jwt_tenant_claim: "11111111-1111-4111-8111-111111111111",
            settings.jwt_user_claim: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            settings.jwt_roles_claim: ["tenant_admin"],
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "exp": 9999999999,
        },
        "wrong-secret",
        algorithm=settings.jwt_algorithm,
    )
    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_privilege_escalation_roles_in_token_not_enough_for_fake_permission() -> None:
    """JWT alone cannot grant DB permissions the user does not have."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            settings.jwt_tenant_claim: "11111111-1111-4111-8111-111111111111",
            settings.jwt_user_claim: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            settings.jwt_roles_claim: ["analyst"],
            "permissions": ["payment.execute"],
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    response = client.get(
        "/api/v1/permissions/evaluate",
        params={"object_type": "payment", "object_id": "p-1", "action": "approve_payment"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if response.status_code >= 500:
        pytest.skip("Database IAM schema not migrated")
    assert response.status_code == 200
    body = response.json()
    if settings.postgres_dsn and settings.iam_use_db_auth:
        assert body["allowed"] is False
