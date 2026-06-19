from app.modules.erp.tax.services.gst_posting_service import build_rcm_journal_lines


def test_rcm_journal_balanced(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.erp.tax.services.gst_posting_service.resolve_account_by_type",
        lambda _org, account_type: "rcm-1" if account_type == "reverse_charge" else None,
    )
    lines = build_rcm_journal_lines(
        "org",
        expense_account_id="exp-1",
        payable_account_id="pay-1",
        invoice_amount=1000,
        gst_lines=[
            {"account_id": "cgst-in", "amount": 90, "tax_code": "CGST_INPUT"},
            {"account_id": "sgst-in", "amount": 90, "tax_code": "SGST_INPUT"},
        ],
    )
    total_dr = sum(l["debit_amount"] for l in lines)
    total_cr = sum(l["credit_amount"] for l in lines)
    assert total_dr == total_cr == 1180.0
    assert lines[-1]["credit_amount"] == 1000
