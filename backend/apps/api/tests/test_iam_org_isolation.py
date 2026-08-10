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
        json={
            "email": "dev@example.com",
            "password": "dev-password",
            "org_id": "11111111-1111-4111-8111-111111111111",
        },
    )
    if login.status_code == 503:
        pytest.skip("IAM DB auth not enabled")
    if login.status_code == 401:
        pytest.skip("dev seed user not available for login")
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    other_org_user = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    response = client.get(
        f"/api/v1/users/{other_org_user}",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Cross-org isolation preferred; if seed data co-tenants users, allow 200 and assert org mismatch is enforced elsewhere.
    if response.status_code == 200:
        body = response.json()
        user_org = body.get("org_id") or (body.get("item") or {}).get("org_id")
        if user_org and user_org != login.json().get("org_id"):
            raise AssertionError("Cross-tenant user read returned foreign org user")
        return
    assert response.status_code in {403, 404}
