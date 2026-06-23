"""Migration readiness smoke tests for architecture remediation migrations."""
from __future__ import annotations

from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[3] / "migrations"


def test_remediation_migrations_present():
    for name in (
        "066_architecture_review_indexes.sql",
        "067_p1_tenancy_hardening.sql",
        "068_p2_scalability_and_tenancy.sql",
    ):
        assert (MIGRATIONS / name).is_file(), f"missing {name}"


def test_migration_068_company_backfill_sql():
    text = (MIGRATIONS / "068_p2_scalability_and_tenancy.sql").read_text(encoding="utf-8")
    assert "DISTINCT ON (org_id)" in text
    assert "chk_erp_journals_company_id_not_null" in text
