from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def test_main_mounts_billing_router() -> None:
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "billing_router" in text


def test_migration_exists() -> None:
    migrations = Path(__file__).resolve().parents[7] / "migrations"
    assert (migrations / "065_billing_engine.sql").is_file()


def test_erp_guards_wired() -> None:
    guards = [
        "modules/erp/accounts_payable/security/ap_guard.py",
        "modules/erp/vouchers/security/voucher_guard.py",
        "modules/erp/consolidation/security/consolidation_guard.py",
    ]
    for rel in guards:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "enforce_billing" in text


def test_finance_os_guards_wired() -> None:
    guards = [
        "modules/finance_os/invoice_ai/security/invoice_ai_guard.py",
        "modules/finance_os/agents/security/agents_guard.py",
        "modules/finance_os/forecasting/security/forecasting_guard.py",
    ]
    for rel in guards:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "enforce_billing" in text


def test_pipeline_billing_hooks() -> None:
    pipe = (ROOT / "modules/finance_os/invoice_ai/pipelines/invoice_pipeline.py").read_text(encoding="utf-8")
    assert "billing_ai_operation" in pipe


def test_event_consumer_gates() -> None:
    ec = (ROOT / "services/event_consumers.py").read_text(encoding="utf-8")
    assert "gate_ai_event" in ec


def test_org_create_bootstraps_billing() -> None:
    admin = (ROOT / "modules/core/iam/routes/admin_routes.py").read_text(encoding="utf-8")
    assert "subscription_service.bootstrap_org" in admin
