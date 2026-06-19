import pytest

from app.modules.erp.tax.validators.gstin_validator import state_from_gstin, validate_gstin


def test_gstin_invalid_raises() -> None:
    with pytest.raises(ValueError):
        validate_gstin("INVALID")


def test_state_from_gstin() -> None:
    assert state_from_gstin("27AABCU9603R1ZM") == "27"
