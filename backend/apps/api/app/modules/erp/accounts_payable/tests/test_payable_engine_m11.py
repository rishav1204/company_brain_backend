from app.modules.erp.accounts_payable.engine.payable_engine import build_liability_journal_lines


def test_liability_journal_balances() -> None:
    lines = build_liability_journal_lines(
        "org",
        expense_account_id="exp-1",
        payable_account_id="pay-1",
        invoice_amount=100000,
        gst_amount=18000,
        total_amount=118000,
        gst_lines=[{"account_id": "gst-1", "amount": 18000, "tax_code": "IGST_INPUT"}],
    )
    debits = sum(l["debit_amount"] for l in lines)
    credits = sum(l["credit_amount"] for l in lines)
    assert round(debits - credits, 2) == 0
    assert any(l["account_id"] == "pay-1" and l["credit_amount"] == 118000 for l in lines)


def test_payment_journal_lines() -> None:
    from app.modules.erp.accounts_payable.engine.payment_engine import build_payment_journal_lines

    lines = build_payment_journal_lines(payable_account_id="p1", bank_account_id="b1", amount=5000)
    assert sum(l["debit_amount"] for l in lines) == sum(l["credit_amount"] for l in lines)
