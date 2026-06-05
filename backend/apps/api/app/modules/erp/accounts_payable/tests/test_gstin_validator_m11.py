import pytest

from app.modules.erp.accounts_payable.validators.gstin_validator import validate_gstin, validate_pan


def test_valid_gstin() -> None:
    validate_gstin("29ABCDE1234F1Z5")


def test_invalid_gstin() -> None:
    with pytest.raises(ValueError):
        validate_gstin("INVALID")


def test_valid_pan() -> None:
    validate_pan("ABCDE1234F")


def test_invalid_pan() -> None:
    with pytest.raises(ValueError):
        validate_pan("12345")
