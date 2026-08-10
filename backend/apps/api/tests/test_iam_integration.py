import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("POSTGRES_DSN", "").strip(),
    reason="POSTGRES_DSN required for IAM integration tests",
)


def test_dev_user_login_and_me() -> None:
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "dev@example.com",
            "password": "dev-password",
            "org_id": "11111111-1111-4111-8111-111111111111",
        },
    )
    if login.status_code == 503:
        pytest.skip("IAM DB auth not enabled")
    assert login.status_code == 200, login.text
    body = login.json()
    token = body["access_token"]
    me = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["user_id"] == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def test_maker_checker_via_permissions_evaluate() -> None:
    from datetime import datetime, timedelta, timezone
    import jwt
    from fastapi.testclient import TestClient
    from app.core.config import settings
    from app.main import app

    client = TestClient(app)
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            settings.jwt_tenant_claim: "11111111-1111-4111-8111-111111111111",
            settings.jwt_user_claim: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            settings.jwt_roles_claim: ["tenant_admin"],
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
        params={
            "object_type": "workflow",
            "object_id": "44444444-4444-4444-8444-444444444441",
            "action": "approve_payment",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    if settings.iam_use_db_auth:
        assert response.json()["allowed"] is False
