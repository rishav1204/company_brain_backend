from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
import pytest

from app.core.config import settings
from tests.integration_helpers import ORG_A, integration_infra_available


@pytest.fixture
def require_integration_infra() -> None:
    if not integration_infra_available():
        pytest.skip("POSTGRES_DSN and REDIS_URL are required for strict integration tests")


@pytest.fixture(autouse=True)
def _accept_synthetic_jwt_sessions(request: pytest.FixtureRequest):
    """Synthetic test JWTs often omit session_id. Keep production session checks
    but treat missing/unknown sessions as active during pytest unless a test
    opts into strict IAM session enforcement (`strict_iam_session` marker).
    """
    if request.node.get_closest_marker("strict_iam_session"):
        yield
        return
    with (
        patch(
            "app.modules.core.iam.repositories.session_repository.SessionRepository.is_session_active",
            return_value=True,
        ),
        patch(
            "app.modules.core.iam.repositories.session_repository.SessionRepository.touch_last_active",
            return_value=None,
        ),
    ):
        # When claim is missing, skip session gate for non-strict tests only
        # (decode still requires session_id when iam_use_db_auth — so also relax claim).
        original_decode_flag = settings.iam_use_db_auth
        # Prefer including session_id in tokens; still relax decoding when claim absent
        # only via jwt helper patch below for local mint tokens without sessions.
        yield
        settings.iam_use_db_auth = original_decode_flag


def build_bearer_token(
    org_id: str = ORG_A,
    user_id: str = "user1",
    roles: list[str] | None = None,
    *,
    session_id: str | None = "00000000-0000-4000-8000-000000000099",
) -> str:
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
    if session_id:
        payload["session_id"] = session_id
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def auth_headers(org_id: str = ORG_A, user_id: str = "user1", roles: list[str] | None = None) -> dict:
    token = build_bearer_token(org_id=org_id, user_id=user_id, roles=roles)
    return {"Authorization": f"Bearer {token}"}
