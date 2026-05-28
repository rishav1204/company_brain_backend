import pytest

from app.modules.platform.documents.validators.upload_validator import validate_upload_payload


def test_upload_validator_accepts_pdf() -> None:
    validate_upload_payload(file_name="invoice.pdf", mime_type="application/pdf", file_size=100)


def test_upload_validator_rejects_large_file() -> None:
    with pytest.raises(ValueError):
        validate_upload_payload(file_name="big.pdf", mime_type="application/pdf", file_size=60 * 1024 * 1024)
