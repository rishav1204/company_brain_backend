from __future__ import annotations

import pytest

from app.modules.erp.coa.services.account_validation_service import account_validation_service


def test_statement_type_validation() -> None:
    account_validation_service.validate_statement_mapping(statement_type="balance_sheet", reporting_category="Assets")
    with pytest.raises(ValueError):
        account_validation_service.validate_statement_mapping(statement_type="unknown", reporting_category="X")


def test_gst_mapping_validation() -> None:
    account_validation_service.validate_gst_mapping(gst_type="cgst_input", itc_eligible=True)
    with pytest.raises(ValueError):
        account_validation_service.validate_gst_mapping(gst_type="cgst_output", itc_eligible=True)

