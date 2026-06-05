import pytest

from app.modules.erp.journals.validators.gst_validator import gst_validator


def test_gst_validator_rejects_unknown_tax_code() -> None:
    with pytest.raises(ValueError, match="Unknown tax_code"):
        gst_validator.validate_lines(
            "org-1",
            [{"account_id": "a1", "tax_code": "INVALID", "debit_amount": 10, "credit_amount": 0}],
        )
