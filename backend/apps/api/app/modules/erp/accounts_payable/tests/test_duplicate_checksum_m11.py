from app.modules.erp.accounts_payable.validators.invoice_validator import build_duplicate_checksum


def test_checksum_stable() -> None:
    a = build_duplicate_checksum(
        vendor_id="v1", invoice_number="INV-1001", total_amount=118000, invoice_date="2026-06-01"
    )
    b = build_duplicate_checksum(
        vendor_id="v1", invoice_number="inv-1001", total_amount=118000.0, invoice_date="2026-06-01"
    )
    assert a == b


def test_checksum_differs_on_amount() -> None:
    a = build_duplicate_checksum(
        vendor_id="v1", invoice_number="INV-1001", total_amount=118000, invoice_date="2026-06-01"
    )
    b = build_duplicate_checksum(
        vendor_id="v1", invoice_number="INV-1001", total_amount=118001, invoice_date="2026-06-01"
    )
    assert a != b
