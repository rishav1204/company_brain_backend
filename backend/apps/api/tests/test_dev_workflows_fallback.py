import jwt
from fastapi.testclient import TestClient

from app.core.config import DEV_ORG_ID
from app.main import app


client = TestClient(app)


def test_dev_workflows_sample_or_live() -> None:
    """Dev password login + workflows list remains callable with sample or live data."""
    login = client.post(
        "/api/v1/auth/password/login",
        json={"email": "dev@example.com", "password": "dev-password"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    response = client.get(
        "/api/v1/workflows?type=ap_invoice&limit=200",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "workflows" in body
    assert body["verification_status"] in {"dev_sample_data", "verified"}
    if body["verification_status"] == "dev_sample_data":
        assert body["items"]
        assert all(item["type"] == "ap_invoice" for item in body["items"])


def test_dev_login_uses_uuid_org_id() -> None:
    response = client.post(
        "/api/v1/auth/password/login",
        json={"email": "dev@example.com", "password": "dev-password"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["org_id"] == DEV_ORG_ID
