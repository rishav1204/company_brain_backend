from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.modules.core.iam.repositories.user_repository import UserRepository


@patch("app.modules.core.iam.repositories.user_repository.get_db_conn")
def test_get_login_bundle_single_connection(mock_get_db) -> None:
    conn = MagicMock()
    cursor = MagicMock()
    mock_get_db.return_value.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchone.return_value = {
        "id": "user-1",
        "org_id": "org-1",
        "email": "dev@example.com",
        "status": "active",
        "password_hash": "hash",
    }
    cursor.fetchall.side_effect = [
        [{"role_name": "tenant_admin", "policy_context": {}, "branch_id": None, "company_id": None, "department_id": None}],
        [{"permission_key": "system.admin"}],
    ]

    repo = UserRepository()
    bundle = repo.get_login_bundle("dev@example.com", org_id="org-1")

    assert bundle is not None
    assert bundle["user"]["id"] == "user-1"
    assert bundle["roles"] == ["tenant_admin"]
    assert bundle["permissions"] == ["system.admin"]
    assert cursor.execute.call_count == 3
    mock_get_db.assert_called_once()


@patch("app.modules.core.iam.repositories.user_repository.get_db_conn")
def test_get_login_bundle_resolves_unique_email_without_org(mock_get_db) -> None:
    conn = MagicMock()
    cursor = MagicMock()
    mock_get_db.return_value.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchall.side_effect = [
        # email-only user lookup (LIMIT 2)
        [
            {
                "id": "user-1",
                "org_id": "org-1",
                "email": "platform.owner@example.com",
                "status": "active",
                "password_hash": "hash",
            }
        ],
        # role rows
        [{"role_name": "platform_owner", "policy_context": {}, "branch_id": None, "company_id": None, "department_id": None}],
        # permissions
        [{"permission_key": "platform.admin"}],
    ]

    repo = UserRepository()
    bundle = repo.get_login_bundle("platform.owner@example.com")

    assert bundle is not None
    assert bundle["user"]["id"] == "user-1"
    assert bundle["roles"] == ["platform_owner"]
    assert "ambiguous" not in bundle


@patch("app.modules.core.iam.repositories.user_repository.get_db_conn")
def test_get_login_bundle_ambiguous_email_requires_org(mock_get_db) -> None:
    conn = MagicMock()
    cursor = MagicMock()
    mock_get_db.return_value.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchall.return_value = [
        {"id": "u1", "org_id": "org-1", "email": "shared@example.com", "status": "active"},
        {"id": "u2", "org_id": "org-2", "email": "shared@example.com", "status": "active"},
    ]

    repo = UserRepository()
    bundle = repo.get_login_bundle("shared@example.com")

    assert bundle == {"ambiguous": True, "match_count": 2}
    # Must not pull roles/permissions for an ambiguous match
    assert cursor.execute.call_count == 1


@patch("app.modules.core.iam.services.auth_service.user_repo.get_login_bundle")
@patch("app.modules.core.iam.services.auth_service.verify_password", return_value=True)
@patch("app.modules.core.iam.services.auth_service.create_refresh_session", return_value=("refresh", "sess-1"))
@patch("app.modules.core.iam.services.auth_service.issue_access_token", return_value=("token", 3600))
@patch("app.modules.core.iam.services.auth_service.assert_mfa_gate")
@patch("app.modules.core.iam.services.auth_service.enforce_concurrent_session_limit")
@patch("app.modules.core.iam.services.auth_service.clear_failures")
@patch("app.modules.core.iam.services.auth_service.require_core_schema")
def test_login_uses_bundle_not_separate_repo_calls(
    _schema,
    _clear,
    _sessions,
    _mfa,
    _issue,
    _refresh,
    _verify,
    mock_bundle,
) -> None:
    mock_bundle.return_value = {
        "user": {
            "id": "user-1",
            "org_id": "org-1",
            "email": "dev@example.com",
            "status": "active",
            "password_hash": "hash",
        },
        "roles": ["tenant_admin"],
        "permissions": ["system.admin"],
        "role_rows": [{"role_name": "tenant_admin", "policy_context": {}}],
    }
    from app.modules.core.iam.services import auth_service

    with patch.object(auth_service, "_defer_login_side_effects"):
        result = auth_service._login_inner("dev@example.com", "pw", None, None, None, None, "org-1", None)

    assert result["access_token"] == "token"
    mock_bundle.assert_called_once_with("dev@example.com", org_id="org-1", org_slug=None)
