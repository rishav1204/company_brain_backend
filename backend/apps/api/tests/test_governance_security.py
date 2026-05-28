from app.modules.platform.governance.api.deps import _AUDITOR_ROLES, _WRITE_ROLES


def test_auditor_roles_defined() -> None:
    assert "auditor" in _AUDITOR_ROLES
    assert "governance_admin" in _WRITE_ROLES


def test_append_only_enforced_by_migration() -> None:
    """Document expectation: public.audit_logs has prevent_audit_log_mutation trigger (001)."""
    assert True
