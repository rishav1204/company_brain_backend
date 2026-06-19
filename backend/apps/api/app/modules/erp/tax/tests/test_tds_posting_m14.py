from app.modules.erp.tax.engine.tds_engine import calculate_tds
from app.modules.erp.tax.services.tds_posting_service import build_payment_journal_lines_no_tds
from app.modules.erp.tax.services.tds_return_service import _build_return_payload


def test_tds_return_payload_builder() -> None:
    txs = [
        {"section_code": "194J", "gross_amount": 100_000, "tds_amount": 10_000},
        {"section_code": "194J", "gross_amount": 50_000, "tds_amount": 5_000},
    ]
    payload = _build_return_payload(form_type="26Q", return_period="2025-04", txs=txs)
    assert payload["summary"]["total_tax"] == 15_000
    assert payload["sections"][0]["count"] == 2


def test_payment_journal_no_tds() -> None:
    lines = build_payment_journal_lines_no_tds(payable_account_id="p", bank_account_id="b", amount=5000)
    assert len(lines) == 2
    assert lines[0]["debit_amount"] == 5000


def test_tds_ytd_threshold() -> None:
    result = calculate_tds(
        gross_amount=20_000,
        rate_pan=10,
        rate_no_pan=20,
        threshold=30_000,
        prior_ytd=15_000,
        pan_present=True,
    )
    assert result["applicable"] is True
    assert result["tds_amount"] == 2_000.0
