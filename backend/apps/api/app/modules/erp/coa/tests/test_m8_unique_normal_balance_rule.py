from __future__ import annotations

import pytest

from app.modules.erp.coa.services.account_validation_service import account_validation_service


def test_group_nature_matches_type() -> None:
    account_validation_service.validate_group(group_type="asset", nature="debit")
    account_validation_service.validate_group(group_type="liability", nature="credit")


def test_group_nature_invalid_raises() -> None:
    with pytest.raises(ValueError):
        account_validation_service.validate_group(group_type="asset", nature="credit")

