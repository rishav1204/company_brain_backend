from app.modules.erp.accounts_receivable.engine.credit_control_engine import credit_check


def test_credit_within_limit() -> None:
    result = credit_check(credit_limit=100000, outstanding=40000, invoice_amount=50000)
    assert result["exceeds_limit"] is False
    assert result["available_credit"] == 60000


def test_credit_exceeds_limit() -> None:
    result = credit_check(credit_limit=100000, outstanding=90000, invoice_amount=20000)
    assert result["exceeds_limit"] is True
    assert result["requires_approval"] is True
