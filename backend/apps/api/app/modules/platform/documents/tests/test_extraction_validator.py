from app.modules.platform.documents.validators.extraction_validator import validate_gst_math


def test_validate_gst_math_passes_when_total_matches() -> None:
    assert validate_gst_math(
        {
            "subtotal": 1000,
            "cgst": 90,
            "sgst": 90,
            "igst": 0,
            "cess": 20,
            "total_amount": 1200,
        }
    )


def test_validate_gst_math_fails_when_total_mismatch() -> None:
    assert not validate_gst_math(
        {
            "subtotal": 1000,
            "cgst": 90,
            "sgst": 90,
            "igst": 0,
            "cess": 20,
            "total_amount": 1300,
        }
    )
