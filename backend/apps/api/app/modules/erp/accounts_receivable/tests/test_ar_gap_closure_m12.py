import pytest

from app.modules.erp.accounts_receivable.services.sales_invoice_service import SalesInvoiceService
from app.modules.erp.accounts_receivable.validators.invoice_validator import invoice_validator


def test_gst_rate_matches_taxable_value() -> None:
    invoice_validator.validate_gst_calculation(taxable_value=1000, gst_rate=0.18, gst_amount=180)


def test_gst_rate_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="does not match"):
        invoice_validator.validate_gst_calculation(taxable_value=1000, gst_rate=0.18, gst_amount=100)


def test_validate_gst_amounts_component_sum() -> None:
    svc = SalesInvoiceService()
    with pytest.raises(ValueError, match="CGST\\+SGST\\+IGST"):
        svc._validate_gst_amounts(
            subtotal=1000,
            gst_amount=180,
            cgst=90,
            sgst=80,
            igst=0,
            gst_rate=0.18,
            export_zero_rated=False,
        )


def test_validate_gst_amounts_export_zero_rated() -> None:
    svc = SalesInvoiceService()
    with pytest.raises(ValueError, match="zero GST"):
        svc._validate_gst_amounts(
            subtotal=1000,
            gst_amount=18,
            cgst=0,
            sgst=0,
            igst=0,
            gst_rate=None,
            export_zero_rated=True,
        )


def test_validate_gst_amounts_with_rate() -> None:
    svc = SalesInvoiceService()
    svc._validate_gst_amounts(
        subtotal=1000,
        gst_amount=180,
        cgst=90,
        sgst=90,
        igst=0,
        gst_rate=0.18,
        export_zero_rated=False,
    )
