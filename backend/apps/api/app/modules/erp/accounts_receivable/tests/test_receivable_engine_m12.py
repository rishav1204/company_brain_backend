from app.modules.erp.accounts_receivable.engine.receivable_engine import build_sales_journal_lines


def test_sales_journal_balances() -> None:
    lines = build_sales_journal_lines(
        "org",
        receivable_account_id="ar-1",
        revenue_account_id="rev-1",
        subtotal=100000,
        gst_amount=18000,
        total_amount=118000,
        gst_lines=[{"account_id": "gst-out", "amount": 18000, "tax_code": "IGST_OUTPUT"}],
    )
    debits = sum(l["debit_amount"] for l in lines)
    credits = sum(l["credit_amount"] for l in lines)
    assert round(debits - credits, 2) == 0
    assert any(l["account_id"] == "ar-1" and l["debit_amount"] == 118000 for l in lines)


def test_receipt_journal_lines() -> None:
    from app.modules.erp.accounts_receivable.engine.collection_engine import build_receipt_journal_lines

    lines = build_receipt_journal_lines(bank_account_id="b1", receivable_account_id="ar1", amount=5000)
    assert sum(l["debit_amount"] for l in lines) == sum(l["credit_amount"] for l in lines)
