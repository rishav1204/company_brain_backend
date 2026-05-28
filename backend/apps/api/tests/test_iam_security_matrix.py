from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def _token(roles: list[str], user_id: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa") -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            settings.jwt_tenant_claim: "11111111-1111-4111-8111-111111111111",
            settings.jwt_user_claim: user_id,
            settings.jwt_roles_claim: roles,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


MATRIX = [
    ("GET", "/api/v1/roles", ["analyst"], {200}),
    ("GET", "/api/v1/users", ["analyst"], {401, 403}),
    ("GET", "/api/v1/permissions", ["analyst"], {200}),
    ("GET", "/api/v1/workflows", ["analyst"], {200, 503}),
    ("POST", "/api/v1/permissions", ["analyst"], {401, 403, 503}),
]


@pytest.mark.parametrize("method,path,roles,allowed", MATRIX)
def test_route_auth_matrix(method: str, path: str, roles: list[str], allowed: set[int]) -> None:
    from app.modules.core.iam.services.iam_schema_service import core_schema_ready

    if path == "/api/v1/users" and not core_schema_ready():
        pytest.skip("IAM schema not migrated")
    client = TestClient(app)
    response = client.request(method, path, headers={"Authorization": f"Bearer {_token(roles)}"})
    assert response.status_code in allowed, (path, roles, response.status_code, response.text[:200])


def test_api_key_rejected_without_scope_on_workflow_action() -> None:
    from app.modules.core.iam.services.iam_schema_service import core_schema_ready

    if not core_schema_ready():
        pytest.skip("IAM schema not migrated")
    client = TestClient(app)
    response = client.post(
        "/api/v1/workflows/44444444-4444-4444-8444-444444444441/actions",
        headers={"Authorization": "Bearer cb_invalid_key_for_test"},
        json={"action": "approve_payment", "parameters": {}},
    )
    assert response.status_code in {401, 403}
