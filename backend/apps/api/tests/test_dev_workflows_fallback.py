import jwt
from fastapi.testclient import TestClient

from app.core.config import DEV_ORG_ID
from app.main import app


client = TestClient(app)


def test_dev_workflows_without_postgres() -> None:
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
    assert body["items"]
    assert body["workflows"]
    assert body["verification_status"] == "dev_sample_data"
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
