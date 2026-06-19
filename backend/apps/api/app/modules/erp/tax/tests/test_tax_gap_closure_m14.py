from app.modules.erp.tax.ai.mismatch_detector import detect_mismatches
from app.modules.erp.tax.engine.gst_engine import build_gst_transaction, split_gst_amount
from app.modules.erp.tax.engine.tds_engine import calculate_tds
from app.modules.erp.tax.services.gst_transaction_service import _resolve_gst_type
from app.modules.erp.tax.services.tds_service import TdsService
from app.modules.erp.tax.services.filing_service import filing_service
from app.services.event_consumers import _handle_tax_workflow_approval


def test_resolve_gst_type_credit_note() -> None:
    assert _resolve_gst_type({"document_type": "credit_note"}, default="purchase", is_ap=True) == "credit_note"


def test_resolve_gst_type_reverse_charge() -> None:
    assert _resolve_gst_type({"reverse_charge": True}, default="purchase", is_ap=True) == "reverse_charge"


def test_split_gst_intra_state() -> None:
    result = split_gst_amount(taxable_value=1000, gst_rate=18, supplier_state="27", place_of_supply="27")
    assert result["cgst_amount"] == 90
    assert result["sgst_amount"] == 90


def test_tds_section_resolution() -> None:
    svc = TdsService()
    section = svc._resolve_section(
        "org",
        vendor={"metadata": {"tds_section": "194J"}},
        payment={"metadata": {}},
    )
    assert section == "194J"


def test_mismatch_vendor_filing_flag() -> None:
    result = detect_mismatches(
        {"cgst_amount": 0, "sgst_amount": 0, "igst_amount": 0, "party_gstin": "27TEST1234F1Z5"},
        {"cgst_amount": 900, "sgst_amount": 900, "igst_amount": 0, "vendor_gstin": "27TEST1234F1Z5"},
    )
    assert "vendor_filing_issue" in result["flags"]


def test_tds_return_calculate_below_threshold() -> None:
    result = calculate_tds(gross_amount=20_000, rate_pan=10, rate_no_pan=20, threshold=30_000)
    assert result["applicable"] is False


def test_tax_workflow_tds_entity() -> None:
    assert _handle_tax_workflow_approval("org", {"entity_type": "other"}) is False


def test_filing_service_facade() -> None:
    assert hasattr(filing_service, "generate_tds_return")
    assert hasattr(filing_service, "generate_gst_return")


def test_build_gst_export_zero() -> None:
    tx = build_gst_transaction(
        gst_type="export",
        taxable_value=1000,
        gst_rate=0,
        supplier_state="27",
        party_gstin=None,
        export_zero_rated=True,
    )
    assert tx["igst_amount"] == 0
