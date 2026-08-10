"""Phase 6 database remediation tests."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[7] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def test_prod_seed_migrations_skipped() -> None:
    from migration_utils import is_seed_migration_skipped_in_prod

    os.environ["APP_ENV"] = "prod"
    assert is_seed_migration_skipped_in_prod("004_benchmark_org_seed.sql") is True
    assert is_seed_migration_skipped_in_prod("078_database_phase6_hardening.sql") is False
    os.environ["MIGRATION_ALLOW_SEEDS_IN_PROD"] = "true"
    assert is_seed_migration_skipped_in_prod("004_benchmark_org_seed.sql") is False
    del os.environ["MIGRATION_ALLOW_SEEDS_IN_PROD"]
    os.environ["APP_ENV"] = "dev"
    assert is_seed_migration_skipped_in_prod("004_benchmark_org_seed.sql") is False


def test_branch_filter_clause() -> None:
    from app.modules.erp.security.branch_scope_sql import branch_filter_clause

    clause, params = branch_filter_clause({"allowed_branch_ids": ["b1", "b2"]})
    assert "branch_id" in clause
    assert params == [["b1", "b2"]]
    clause2, params2 = branch_filter_clause({})
    assert clause2 == ""
    assert params2 == []


def test_company_resolution_single_company(monkeypatch) -> None:
    from app.modules.erp.security.company_resolution_service import company_resolution_service

    monkeypatch.setattr(
        "app.modules.erp.security.company_resolution_service.organization_repository.list_companies",
        lambda org_id, limit=10: [{"id": "c1"}],
    )
    resolved = company_resolution_service.resolve_for_write(
        "org-1", company_id=None, operation="journal.create_draft"
    )
    assert resolved == "c1"


def test_company_resolution_multi_company_requires_explicit() -> None:
    from app.modules.erp.security.company_resolution_service import company_resolution_service
    from app.modules.core.iam.repositories.organization_repository import organization_repository

    class _Stub:
        def list_companies(self, org_id: str, limit: int = 10) -> list[dict]:
            return [{"id": "c1"}, {"id": "c2"}]

    company_resolution_service.__dict__["_stub"] = _Stub()
    orig = organization_repository.list_companies
    organization_repository.list_companies = _Stub().list_companies  # type: ignore[method-assign]
    try:
        try:
            company_resolution_service.resolve_for_write(
                "org-1", company_id=None, operation="journal.create_draft"
            )
            raised = False
        except ValueError as exc:
            raised = True
            assert "company_id is required" in str(exc)
        assert raised
    finally:
        organization_repository.list_companies = orig  # type: ignore[method-assign]


def test_subledger_gl_reconciliation_service_import() -> None:
    from app.modules.erp.reconciliation.services.subledger_gl_reconciliation_service import (
        subledger_gl_reconciliation_service,
    )

    assert callable(subledger_gl_reconciliation_service.run_daily)


def test_security_validation_erp_company_id_in_prod(monkeypatch) -> None:
    from app.core import security_validation
    from app.core.config import settings

    monkeypatch.setattr(settings, "app_env", "prod")
    monkeypatch.setattr(settings, "jwt_secret", "x" * 32)
    monkeypatch.setattr(settings, "auth_mode", "bearer_only")
    monkeypatch.setattr(settings, "oidc_enabled", True)
    monkeypatch.setattr(settings, "allow_password_auth_in_prod", False)
    monkeypatch.setattr(settings, "api_key_pepper", "pepper")
    monkeypatch.setattr(settings, "redis_url", "redis://localhost")
    monkeypatch.setattr(settings, "redis_require_tls", True)
    monkeypatch.setattr(settings, "neo4j_password", "secure-password")
    monkeypatch.setattr(settings, "clamav_enabled", False)
    monkeypatch.setattr(settings, "integrations_credentials_key", "key")
    monkeypatch.setattr(settings, "erp_require_company_id", False)

    ok, issues = security_validation.validate_prod_security()
    assert not ok
    assert "erp_require_company_id_must_be_true_in_prod" in issues
