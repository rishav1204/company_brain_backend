from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def test_main_mounts_voucher_router() -> None:
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "erp_vouchers_router" in text


def test_projection_hooks_wired() -> None:
    ap = (ROOT / "modules" / "erp" / "accounts_payable" / "services" / "invoice_service.py").read_text(encoding="utf-8")
    ar = (ROOT / "modules" / "erp" / "accounts_receivable" / "services" / "sales_invoice_service.py").read_text(encoding="utf-8")
    pay = (ROOT / "modules" / "erp" / "accounts_payable" / "services" / "payment_service.py").read_text(encoding="utf-8")
    rec = (ROOT / "modules" / "erp" / "accounts_receivable" / "services" / "collection_service.py").read_text(encoding="utf-8")
    bank = (ROOT / "modules" / "erp" / "banking" / "services" / "payment_execution_service.py").read_text(encoding="utf-8")
    assert "voucher_projection_service.project_operational" in ap
    assert "voucher_projection_service.project_operational" in ar
    assert "voucher_projection_service.project_operational" in pay
    assert "voucher_projection_service.project_operational" in rec
    assert "voucher_projection_service.project_operational" in bank


def test_journal_generation_is_sole_m10_bridge() -> None:
    jgs = (ROOT / "modules" / "erp" / "vouchers" / "services" / "journal_generation_service.py").read_text(encoding="utf-8")
    assert "journal_service.create_draft" in jgs
    assert "posting_orchestrator" not in jgs
    assert "ledger_entries" not in jgs


def test_m25_pipeline_draft_hook() -> None:
    pipe = (ROOT / "modules" / "finance_os" / "invoice_ai" / "pipelines" / "invoice_pipeline.py").read_text(encoding="utf-8")
    assert "create_from_extraction" in pipe


def test_ap_ar_note_routes() -> None:
    ap_routes = (ROOT / "modules" / "erp" / "accounts_payable" / "routes" / "invoice_routes.py").read_text(encoding="utf-8")
    ar_routes = (ROOT / "modules" / "erp" / "accounts_receivable" / "routes" / "invoice_routes.py").read_text(encoding="utf-8")
    assert "/credit-note" in ap_routes
    assert "/debit-note" in ap_routes
    assert "/credit-note" in ar_routes
    assert "/debit-note" in ar_routes
