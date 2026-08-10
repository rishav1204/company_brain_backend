from app.modules.finance_os.invoice_ai.review.invoice_reviewer import review_invoice_extraction


def test_suspicious_gst_without_gstin() -> None:
    result = review_invoice_extraction({"gst_amount": 1800, "vendor": "ABC Pvt Ltd", "total_amount": 11800, "subtotal": 10000})
    assert result["requires_review"] is True
    assert any(f["type"] == "suspicious_gst" for f in result["flags"])


def test_clean_invoice_no_flags() -> None:
    result = review_invoice_extraction({
        "vendor": "ABC Pvt Ltd",
        "gstin": "29ABCDE1234F1Z5",
        "subtotal": 10000,
        "total_amount": 11800,
        "gst_amount": 1800,
    })
    assert result["flag_count"] == 0
