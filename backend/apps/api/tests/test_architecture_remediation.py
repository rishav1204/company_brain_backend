"""Architecture remediation regression tests."""
from __future__ import annotations

from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def test_gl_post_routes_through_orchestrator():
    text = (APP / "modules" / "erp" / "gl" / "routes" / "posting_routes.py").read_text(encoding="utf-8")
    assert "posting_orchestrator" in text
    assert "posting_service.post" not in text


def test_db_connection_pool_present():
    text = (APP / "services" / "db.py").read_text(encoding="utf-8")
    assert "ConnectionPool" in text


def test_ap_payment_atomic_conn_path():
    text = (APP / "modules" / "erp" / "accounts_payable" / "services" / "payment_service.py").read_text(
        encoding="utf-8"
    )
    assert "post_journal_with_conn" in text
    assert "record_payment_debit_conn" in text


def test_ar_receipt_atomic_conn_path():
    text = (APP / "modules" / "erp" / "accounts_receivable" / "services" / "collection_service.py").read_text(
        encoding="utf-8"
    )
    assert "post_journal_with_conn" in text
    assert "record_receipt_credit_conn" in text


def test_event_consumers_modular_package():
    consumers = APP / "modules" / "platform" / "events" / "consumers"
    assert (consumers / "erp_consumer.py").is_file()
    assert (consumers / "workflow_consumer.py").is_file()
    assert (consumers / "finance_os_consumer.py").is_file()
    assert (consumers / "ingestion_consumer.py").is_file()


def test_migration_068_present():
    migrations = Path(__file__).resolve().parents[3] / "migrations"
    assert (migrations / "068_p2_scalability_and_tenancy.sql").is_file()


def test_ledger_balance_accumulates_closing_balance():
    text = (APP / "modules" / "erp" / "gl" / "repositories" / "ledger_repository.py").read_text(encoding="utf-8")
    assert "closing_balance = erp.account_balances.closing_balance + EXCLUDED.closing_balance" in text


def test_gl_reversal_routes_through_posting_service():
    text = (APP / "modules" / "erp" / "gl" / "services" / "reversal_service.py").read_text(encoding="utf-8")
    assert "posting_service.post_with_conn" in text
    assert "ledger_repository.insert_entries" not in text


def test_gl_post_journal_type_is_general():
    text = (APP / "modules" / "erp" / "gl" / "routes" / "posting_routes.py").read_text(encoding="utf-8")
    assert 'journal_type="general"' in text
