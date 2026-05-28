from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import settings
from tests.integration_helpers import ORG_A, integration_infra_available


@pytest.fixture
def require_integration_infra() -> None:
    if not integration_infra_available():
        pytest.skip("POSTGRES_DSN and REDIS_URL are required for strict integration tests")


def build_bearer_token(org_id: str = ORG_A, user_id: str = "user1", roles: list[str] | None = None) -> str:
    resolved_roles = roles or ["tenant_admin"]
    now = datetime.now(timezone.utc)
    payload = {
        settings.jwt_tenant_claim: org_id,
        settings.jwt_user_claim: user_id,
        settings.jwt_roles_claim: resolved_roles,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def auth_headers(org_id: str = ORG_A, user_id: str = "user1", roles: list[str] | None = None) -> dict:
    token = build_bearer_token(org_id=org_id, user_id=user_id, roles=roles)
    return {"Authorization": f"Bearer {token}"}
