import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("POSTGRES_DSN", "").strip(),
    reason="POSTGRES_DSN required for org isolation integration test",
)


def test_tenant_cannot_read_other_org_user() -> None:
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "dev@example.com", "password": "dev-password"},
    )
    if login.status_code == 503:
        pytest.skip("IAM DB auth not enabled")
    assert login.status_code == 200
    token = login.json()["access_token"]
    other_org_user = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    response = client.get(
        f"/api/v1/users/{other_org_user}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code in {403, 404}
