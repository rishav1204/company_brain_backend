from app.modules.finance_os.domain_intelligence.ap.vendor_risk import assess_vendor_risk


def test_vendor_risk_overdue_invoices() -> None:
    result = assess_vendor_risk(
        "org",
        vendor_id="v1",
        invoices=[
            {"status": "approved", "total_amount": 1000, "paid_amount": 0, "due_date": "2020-01-01"},
            {"status": "approved", "total_amount": 500, "paid_amount": 0, "due_date": "2020-02-01"},
        ],
        payments=[],
    )
    assert result["overdue_invoices"] >= 2
    assert result["risk_level"] in {"medium", "high"}
