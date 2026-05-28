import os

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _set_env(name: str, value: str) -> str | None:
    prior = os.environ.get(name)
    os.environ[name] = value
    return prior


def _restore_env(name: str, prior: str | None) -> None:
    if prior is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = prior


def test_dev_password_login_without_auth_headers() -> None:
    from app.core.config import settings

    prev_app_env = settings.app_env
    prev_enable = settings.enable_dev_auth_routes
    prev_disable = settings.disable_dev_auth_routes_in_prod
    prev_auth_mode = settings.auth_mode
    settings.app_env = "dev"
    settings.enable_dev_auth_routes = True
    settings.disable_dev_auth_routes_in_prod = True
    settings.auth_mode = "bearer_only"
    try:
        response = client.post(
            "/api/v1/auth/password/login",
            json={"email": "test@example.com", "password": "dev-password", "org_id": "org-demo", "roles": ["tenant_admin"]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["access_token"]
        assert body["verification_status"] == "dev_password_exchange"
    finally:
        settings.app_env = prev_app_env
        settings.enable_dev_auth_routes = prev_enable
        settings.disable_dev_auth_routes_in_prod = prev_disable
        settings.auth_mode = prev_auth_mode


def test_dev_password_login_middleware_allows_stripped_proxy_path() -> None:
    response = client.post(
        "/auth/password/login",
        json={"email": "test@example.com", "password": "dev-password"},
    )
    assert response.status_code != 401
    assert response.json().get("detail") != "Missing authenticated org or bearer token"


def test_dev_auth_disabled_in_prod() -> None:
    prev_env = _set_env("APP_ENV", "prod")
    prev_toggle = _set_env("DISABLE_DEV_AUTH_ROUTES_IN_PROD", "true")
    try:
        from app.core.config import settings

        prev_app_env = settings.app_env
        prev_disable = settings.disable_dev_auth_routes_in_prod
        prev_enable = settings.enable_dev_auth_routes
        prev_auth_mode = settings.auth_mode
        settings.app_env = "prod"
        settings.disable_dev_auth_routes_in_prod = True
        settings.enable_dev_auth_routes = True
        settings.auth_mode = "bearer_only"
        response = client.post(
            "/api/v1/auth/password/login",
            json={"email": "test@example.com", "password": "dev-password", "org_id": "org-demo", "roles": ["tenant_admin"]},
        )
        assert response.status_code in {401, 404}
    finally:
        from app.core.config import settings

        settings.app_env = prev_app_env
        settings.disable_dev_auth_routes_in_prod = prev_disable
        settings.enable_dev_auth_routes = prev_enable
        settings.auth_mode = prev_auth_mode
        _restore_env("APP_ENV", prev_env)
        _restore_env("DISABLE_DEV_AUTH_ROUTES_IN_PROD", prev_toggle)

