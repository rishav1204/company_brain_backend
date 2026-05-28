from __future__ import annotations

import pytest

from app.modules.erp.coa.services.import_export_service import import_export_service


class _Row:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_import_rejects_duplicate_codes() -> None:
    rows = [
        _Row(
            group_code="G1",
            group_name="Assets",
            group_type="asset",
            nature="debit",
            parent_group_code=None,
            account_code="A1",
            account_name="Cash",
            account_type="cash",
            parent_account_code=None,
            is_postable=True,
            currency_code="INR",
        ),
        _Row(
            group_code="G1",
            group_name="Assets",
            group_type="asset",
            nature="debit",
            parent_group_code=None,
            account_code="A2",
            account_name="Bank",
            account_type="bank",
            parent_account_code=None,
            is_postable=True,
            currency_code="INR",
        ),
    ]
    with pytest.raises(ValueError):
        import_export_service.import_coa("00000000-0000-0000-0000-000000000000", rows=rows)

