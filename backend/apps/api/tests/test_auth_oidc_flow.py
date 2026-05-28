from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import auth_headers


client = TestClient(app)
headers = auth_headers(org_id="org-demo", user_id="user1", roles=["tenant_admin"])


def test_oidc_start_disabled_by_default() -> None:
    from app.core.config import settings

    prev = settings.oidc_enabled
    settings.oidc_enabled = False
    try:
        response = client.get("/api/v1/auth/oidc/start", headers=headers)
        assert response.status_code == 404
    finally:
        settings.oidc_enabled = prev


def test_oidc_start_requires_config_when_enabled() -> None:
    from app.core.config import settings

    prev_enabled = settings.oidc_enabled
    prev_authorize = settings.oidc_authorization_endpoint
    prev_client_id = settings.oidc_client_id
    prev_redirect = settings.oidc_redirect_uri
    settings.oidc_enabled = True
    settings.oidc_authorization_endpoint = ""
    settings.oidc_client_id = ""
    settings.oidc_redirect_uri = ""
    try:
        response = client.get("/api/v1/auth/oidc/start", headers=headers)
        assert response.status_code == 503
    finally:
        settings.oidc_enabled = prev_enabled
        settings.oidc_authorization_endpoint = prev_authorize
        settings.oidc_client_id = prev_client_id
        settings.oidc_redirect_uri = prev_redirect


def test_oidc_refresh_rejects_malformed_token() -> None:
    from app.core.config import settings

    prev = settings.oidc_enabled
    settings.oidc_enabled = True
    try:
        response = client.post("/api/v1/auth/oidc/refresh", headers=headers, json={"refresh_token": "bad"})
        assert response.status_code == 401
    finally:
        settings.oidc_enabled = prev


def test_oidc_logout_endpoint_when_enabled() -> None:
    from app.core.config import settings

    prev = settings.oidc_enabled
    settings.oidc_enabled = True
    try:
        response = client.post("/api/v1/auth/oidc/logout", headers=headers, json={})
        assert response.status_code == 200
        assert response.json()["status"] == "logged_out"
    finally:
        settings.oidc_enabled = prev
