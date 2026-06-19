from app.modules.erp.tax.engine.filing_engine import build_gstr1_payload, build_gstr3b_payload, build_gstr9_payload
from app.modules.erp.tax.engine.gst_engine import split_gst_amount
from app.modules.erp.tax.services.gst_calculation_service import gst_calculation_service


def test_gstr1_payload() -> None:
    txs = [{
        "gst_type": "sales", "party_gstin": "27AABCU9603R1ZM", "invoice_date": "2026-06-01",
        "taxable_value": 1000, "cgst_amount": 90, "sgst_amount": 90, "igst_amount": 0, "source_id": "inv1",
    }]
    payload = build_gstr1_payload(txs, return_period="2026-06")
    assert payload["return_type"] == "GSTR-1"
    assert len(payload["b2b"]) == 1


def test_gstr1_b2c_and_exports() -> None:
    txs = [
        {"gst_type": "sales", "party_gstin": None, "taxable_value": 100, "cgst_amount": 9, "sgst_amount": 9, "igst_amount": 0},
        {"gst_type": "export", "taxable_value": 5000, "cgst_amount": 0, "sgst_amount": 0, "igst_amount": 0},
        {"gst_type": "credit_note", "party_gstin": "27AABCU9603R1ZM", "taxable_value": 200, "cgst_amount": 18, "sgst_amount": 18, "igst_amount": 0},
    ]
    payload = build_gstr1_payload(txs, return_period="2026-06")
    assert len(payload["b2c_small"]) == 1
    assert len(payload["exports"]) == 1
    assert len(payload["credit_notes"]) == 1


def test_gstr3b_payload() -> None:
    txs = [
        {"gst_type": "sales", "cgst_amount": 90, "sgst_amount": 90, "igst_amount": 0},
        {"gst_type": "purchase", "cgst_amount": 50, "sgst_amount": 50, "igst_amount": 0},
    ]
    payload = build_gstr3b_payload(txs, return_period="2026-06", itc_claimed=80)
    assert payload["output_tax"] == 180.0
    assert payload["input_tax"] == 100.0
    assert payload["section_3_1_tax_liability"] == 180.0


def test_gstr9_payload() -> None:
    txs = [
        {"gst_type": "sales", "taxable_value": 1000, "cgst_amount": 90, "sgst_amount": 90, "igst_amount": 0},
        {"gst_type": "purchase", "taxable_value": 500, "cgst_amount": 45, "sgst_amount": 45, "igst_amount": 0},
    ]
    payload = build_gstr9_payload(txs, financial_year="2025")
    assert payload["return_type"] == "GSTR-9"
    assert payload["outward_supplies"]["taxable_value"] == 1000.0


def test_gst_calculate_service_intrastate() -> None:
    result = gst_calculation_service.calculate(
        "org",
        taxable_value=1000,
        gst_rate=18,
        supplier_state="29",
        place_of_supply="29",
    )
    assert result["cgst_amount"] == 90.0
    assert result["sgst_amount"] == 90.0
    assert result["total_tax"] == 180.0


def test_gst_calculate_service_interstate() -> None:
    result = gst_calculation_service.calculate(
        "org",
        taxable_value=1000,
        gst_rate=18,
        supplier_state="29",
        place_of_supply="27",
    )
    assert result["igst_amount"] == 180.0
    assert result["supply_type"] == "interstate"


def test_split_gst_intrastate() -> None:
    split = split_gst_amount(taxable_value=1000, gst_rate=18, supplier_state="29", place_of_supply="29")
    assert split["cgst_amount"] == 90.0
    assert split["sgst_amount"] == 90.0
