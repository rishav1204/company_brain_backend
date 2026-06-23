"""Tests for ERP company scope guard."""
from __future__ import annotations

import pytest

from app.modules.erp.security.company_scope import require_company_id_for_erp_write


def test_require_company_id_raises_when_missing():
    with pytest.raises(ValueError, match="company_id is required"):
        require_company_id_for_erp_write(org_id="11111111-1111-4111-8111-111111111111", company_id=None, operation="post")


def test_require_company_id_returns_normalized():
    cid = require_company_id_for_erp_write(
        org_id="11111111-1111-4111-8111-111111111111",
        company_id=" 22222222-2222-4222-8222-222222222222 ",
        operation="post",
    )
    assert cid == "22222222-2222-4222-8222-222222222222"
