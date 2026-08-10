"""Behaviour that must hold for the cross-tenant operator console.

The risky part of this module is not the SQL, it is the blast radius: it can
change IAM state in an org the caller does not belong to. These tests pin the
guardrails around that.
"""
import pytest

from app.modules.platform.operator.services.operator_service import (
    OperatorError,
    OperatorService,
    UserNotFound,
)

ACTOR_ID = "0f000001-0001-4001-8001-00000000000f"
ACTOR_ORG = "11111111-1111-4111-8111-111111111111"
TARGET_ID = "99999999-9999-4999-8999-999999999999"
TARGET_ORG = "22222222-2222-4222-8222-222222222222"

TARGET_USER = {
    "user_id": TARGET_ID,
    "org_id": TARGET_ORG,
    "org_name": "Tenant B Org",
    "email": "user@tenant-b.example",
    "display_name": "Tenant B User",
    "status": "active",
}


class _Recorder:
    def __init__(self, user=TARGET_USER):
        self.user = user
        self.status_calls = []
        self.revoke_calls = []
        self.audit_calls = []

    # operator_repository
    def find_user(self, user_id):
        return dict(self.user) if self.user and user_id == self.user["user_id"] else None

    # user_repo
    def update_status(self, org_id, user_id, status):
        self.status_calls.append((org_id, user_id, status))
        return {"id": user_id, "org_id": org_id, "email": self.user["email"], "status": status}

    # session_repo
    def revoke_all_for_user(self, org_id, user_id):
        self.revoke_calls.append((org_id, user_id))
        return 3

    # audit_repo
    def create_log(self, **kwargs):
        self.audit_calls.append(kwargs)
        return {}


@pytest.fixture
def service():
    rec = _Recorder()
    svc = OperatorService(repository=rec, users=rec, sessions=rec, audit=rec)
    svc.recorder = rec
    return svc


def test_suspend_targets_the_users_own_org_not_the_actors(service) -> None:
    service.set_user_status(
        user_id=TARGET_ID, status="suspended", actor_user_id=ACTOR_ID, actor_org_id=ACTOR_ORG
    )
    org_used, _, status = service.recorder.status_calls[0]
    assert org_used == TARGET_ORG, "must write into the target tenant, not the operator's org"
    assert status == "suspended"


def test_suspend_revokes_live_sessions(service) -> None:
    result = service.set_user_status(
        user_id=TARGET_ID, status="suspended", actor_user_id=ACTOR_ID, actor_org_id=ACTOR_ORG
    )
    assert service.recorder.revoke_calls == [(TARGET_ORG, TARGET_ID)]
    assert result["sessions_revoked"] == 3


def test_reactivate_does_not_revoke_sessions(service) -> None:
    service.set_user_status(
        user_id=TARGET_ID, status="active", actor_user_id=ACTOR_ID, actor_org_id=ACTOR_ORG
    )
    assert service.recorder.revoke_calls == []


def test_operator_cannot_change_own_status(service) -> None:
    with pytest.raises(OperatorError, match="lock yourself out"):
        service.set_user_status(
            user_id=ACTOR_ID, status="suspended", actor_user_id=ACTOR_ID, actor_org_id=ACTOR_ORG
        )
    assert service.recorder.status_calls == []


def test_invalid_status_is_rejected_before_any_write(service) -> None:
    with pytest.raises(OperatorError):
        service.set_user_status(
            user_id=TARGET_ID, status="banned", actor_user_id=ACTOR_ID, actor_org_id=ACTOR_ORG
        )
    assert service.recorder.status_calls == []


def test_unknown_user_raises_not_found(service) -> None:
    with pytest.raises(UserNotFound):
        service.set_user_status(
            user_id="00000000-0000-4000-8000-000000000000",
            status="suspended",
            actor_user_id=ACTOR_ID,
            actor_org_id=ACTOR_ORG,
        )


def test_action_is_audited_into_the_target_tenant(service) -> None:
    service.set_user_status(
        user_id=TARGET_ID, status="suspended", actor_user_id=ACTOR_ID, actor_org_id=ACTOR_ORG
    )
    entry = service.recorder.audit_calls[0]
    assert entry["org_id"] == TARGET_ORG
    assert entry["actor_type"] == "platform_operator"
    assert entry["actor_id"] == ACTOR_ID
    assert entry["event_type"] == "platform.user.status_changed"
    assert entry["payload_jsonb"]["cross_org"] is True
    assert entry["payload_jsonb"]["previous_status"] == "active"


def test_revoke_sessions_is_audited_and_scoped_to_target_org(service) -> None:
    result = service.revoke_all_sessions(
        user_id=TARGET_ID, actor_user_id=ACTOR_ID, actor_org_id=ACTOR_ORG
    )
    assert result["sessions_revoked"] == 3
    assert service.recorder.revoke_calls == [(TARGET_ORG, TARGET_ID)]
    entry = service.recorder.audit_calls[0]
    assert entry["org_id"] == TARGET_ORG
    assert entry["event_type"] == "platform.user.sessions_revoked"


def test_routes_require_platform_admin_permission() -> None:
    """The gate must be the permission itself: permission_guard grants a
    tenant_admin fallback only for keys in _TENANT_ADMIN_ALLOWED, and
    platform.admin must never be added to that set."""
    from app.modules.core.iam.middleware.permission_guard import _TENANT_ADMIN_ALLOWED
    from app.modules.platform.operator.routes import operator_routes

    assert "platform.admin" not in _TENANT_ADMIN_ALLOWED

    paths = {route.path for route in operator_routes.router.routes}
    assert paths == {
        "/ops/platform/orgs",
        "/ops/platform/users",
        "/ops/platform/usage",
        "/ops/platform/users/{user_id}/status",
        "/ops/platform/users/{user_id}/sessions/revoke-all",
    }
