from app.modules.erp.tax.engine.tds_engine import (
    calculate_tds,
    financial_year_from_date,
    quarter_from_date,
    resolve_effective_rate,
)
from app.modules.erp.tax.engine.tcs_engine import calculate_tcs
from app.modules.erp.tax.services.tds_posting_service import build_payment_journal_lines


def test_tds_194j_calculation() -> None:
    result = calculate_tds(gross_amount=100_000, rate_pan=10, rate_no_pan=20, threshold=30_000, pan_present=True)
    assert result["tds_amount"] == 10_000.0
    assert result["net_amount"] == 90_000.0


def test_tds_below_threshold() -> None:
    result = calculate_tds(gross_amount=20_000, rate_pan=10, rate_no_pan=20, threshold=30_000)
    assert result["applicable"] is False
    assert result["tds_amount"] == 0.0


def test_tds_no_pan_higher_rate() -> None:
    result = calculate_tds(gross_amount=100_000, rate_pan=10, rate_no_pan=20, threshold=0, pan_present=False)
    assert result["tds_amount"] == 20_000.0
    assert result["rate"] == 20.0


def test_resolve_effective_rate_no_pan_minimum() -> None:
    assert resolve_effective_rate(rate_pan=5, rate_no_pan=10, pan_present=False) == 20.0


def test_financial_year_april() -> None:
    assert financial_year_from_date("2025-04-01") == "2025-2026"
    assert financial_year_from_date("2025-03-31") == "2024-2025"


def test_quarter_from_date() -> None:
    assert quarter_from_date("2025-05-15") == "Q1"
    assert quarter_from_date("2025-11-01") == "Q3"


def test_tcs_calculation() -> None:
    result = calculate_tcs(gross_amount=100_000, rate_pan=0.1, rate_no_pan=1, threshold=0, pan_present=True)
    assert result["tcs_amount"] == 100.0
    assert result["total_collected"] == 100_100.0


def test_payment_journal_with_tds() -> None:
    lines = build_payment_journal_lines(
        payable_account_id="pay-1",
        bank_account_id="bank-1",
        tds_payable_account_id="tds-1",
        gross_amount=100_000,
        tds_amount=10_000,
        net_amount=90_000,
    )
    assert len(lines) == 3
    assert lines[0]["debit_amount"] == 100_000
    assert lines[1]["credit_amount"] == 90_000
    assert lines[2]["credit_amount"] == 10_000
