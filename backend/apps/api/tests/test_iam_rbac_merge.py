from unittest.mock import patch

from app.modules.core.iam.services.rbac_service import merge_policy_context


@patch("app.modules.core.iam.services.rbac_service.role_repo.list_user_roles")
def test_merge_policy_unlimited_when_any_role_uncapped(mock_roles) -> None:
    mock_roles.return_value = [
        {"policy_context": {"max_approve_amount": None}},
        {"policy_context": {"max_approve_amount": 500000}},
    ]
    attrs = merge_policy_context("org-1", "user-1")
    assert "max_approve_amount" not in attrs


@patch("app.modules.core.iam.services.rbac_service.role_repo.list_user_roles")
def test_merge_policy_uses_max_of_capped_roles(mock_roles) -> None:
    mock_roles.return_value = [
        {"policy_context": {"max_approve_amount": 500000}},
        {"policy_context": {"max_approve_amount": 1000000}},
    ]
    attrs = merge_policy_context("org-1", "user-1")
    assert attrs["max_approve_amount"] == 1000000
