"""Phase 1 enterprise IAM infrastructure tests."""

from __future__ import annotations

import hashlib
from unittest.mock import patch

import pytest

from app.modules.core.iam.services.branch_scope_service import evaluate_branch_scope
from app.modules.core.iam.services.device_trust_service import device_fingerprint_from_request
from app.modules.core.iam.services.rbac_service import merge_policy_context
from app.modules.core.iam.validators.password_validator import validate_password_strength
from app.modules.platform.governance.engine.sod_engine import check_role_conflicts


def test_password_policy_requires_special_char() -> None:
    with pytest.raises(ValueError, match="special"):
        validate_password_strength("LongPassword1")


def test_device_fingerprint_stable() -> None:
    fp1 = device_fingerprint_from_request(user_agent="Mozilla/5.0")
    fp2 = device_fingerprint_from_request(user_agent="Mozilla/5.0")
    assert fp1 == fp2
    assert len(fp1) == 64


def test_department_scope_denied() -> None:
    decision = evaluate_branch_scope(
        attrs={"allowed_department_ids": ["dept-a"]},
        object_branch_id=None,
        object_company_id=None,
        object_department_id="dept-b",
    )
    assert decision is not None
    assert not decision.allowed
    assert decision.reason == "department_scope_denied"


def test_merge_policy_context_department_ids() -> None:
    rows = [
        {"policy_context": {}, "branch_id": None, "company_id": None, "department_id": "d1"},
        {"policy_context": {}, "branch_id": None, "company_id": None, "department_id": "d2"},
    ]
    with patch("app.modules.core.iam.services.rbac_service.role_repo") as mock_repo:
        mock_repo.list_user_roles.return_value = rows
        merged = merge_policy_context("org", "user")
    assert merged["allowed_department_ids"] == ["d1", "d2"]


def test_sod_role_conflict_detection() -> None:
    with patch(
        "app.modules.platform.governance.repositories.sod_conflict_repository.sod_conflict_repo.list_conflicts",
        return_value=[{"role_a": "ap_clerk", "role_b": "ap_approver"}],
    ):
        reason = check_role_conflicts(org_id="org", role_names=["ap_clerk", "ap_approver"])
    assert reason is not None
    assert "SoD conflict" in reason


def test_oidc_complete_login_requires_iam_user(monkeypatch) -> None:
    from app.modules.core.iam.services.auth_service import AuthError
    from app.modules.core.iam.services.oidc_service import IamOidcService

    svc = IamOidcService()
    with patch("app.modules.core.iam.services.auth_service.iam_db_enabled", return_value=True):
        with patch("app.modules.core.iam.services.oidc_user_resolver.resolve_oidc_user", return_value=None):
            with pytest.raises(AuthError):
                svc.complete_login({"sub": "x", "email": "a@b.com"})
