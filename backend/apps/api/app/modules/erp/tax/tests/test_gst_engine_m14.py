from app.modules.erp.tax.engine.gst_engine import build_gst_transaction, is_intra_state, split_gst_amount
from app.modules.erp.tax.validators.gstin_validator import validate_gstin


def test_validate_gstin_valid() -> None:
    assert validate_gstin("27AABCU9603R1ZM") == "27AABCU9603R1ZM"


def test_intra_state_cgst_sgst_split() -> None:
    split = split_gst_amount(taxable_value=1000, gst_rate=18, supplier_state="27", place_of_supply="27")
    assert split["cgst_amount"] == 90.0
    assert split["sgst_amount"] == 90.0
    assert split["igst_amount"] == 0.0


def test_inter_state_igst_split() -> None:
    split = split_gst_amount(taxable_value=1000, gst_rate=18, supplier_state="27", place_of_supply="09")
    assert split["igst_amount"] == 180.0
    assert split["cgst_amount"] == 0.0


def test_export_zero_rated() -> None:
    tx = build_gst_transaction(
        gst_type="sales",
        taxable_value=10000,
        gst_rate=18,
        supplier_state="27",
        party_gstin=None,
        export_zero_rated=True,
    )
    assert tx["gst_type"] == "export"
    assert tx["igst_amount"] == 0.0


def test_is_intra_state() -> None:
    assert is_intra_state("27", "27") is True
    assert is_intra_state("27", "09") is False
