from app.modules.finance_os.domain_intelligence.tax.mismatch_detector import detect_mismatches
from app.modules.erp.tax.engine.reconciliation_engine import match_2b_row


def test_2b_match_high_confidence() -> None:
    our = {"party_gstin": "27AABCU9603R1ZM", "cgst_amount": 90, "sgst_amount": 90, "metadata": {"invoice_number": "INV-1"}}
    g2b = {"vendor_gstin": "27AABCU9603R1ZM", "invoice_ref": "INV-1", "cgst_amount": 90, "sgst_amount": 90}
    result = match_2b_row(our, g2b)
    assert result["confidence_score"] >= 0.7
    assert result["match_status"] == "matched"


def test_mismatch_detector_gst_difference() -> None:
    our = {"party_gstin": "27AABCU9603R1ZM", "cgst_amount": 90, "sgst_amount": 90}
    g2b = {"cgst_amount": 50, "sgst_amount": 50}
    flags = detect_mismatches(our, g2b)
    assert "gst_difference" in flags["flags"]
