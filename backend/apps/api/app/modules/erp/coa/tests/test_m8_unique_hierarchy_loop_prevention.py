from __future__ import annotations

import pytest

from app.modules.erp.coa.services.account_validation_service import account_validation_service


def test_detects_loop() -> None:
    chain = {"A": "B", "B": "A"}
    with pytest.raises(ValueError):
        account_validation_service.ensure_no_hierarchy_loop(node_id="A", parent_id="B", parent_chain=chain)


def test_allows_acyclic() -> None:
    chain = {"A": None, "B": "A"}
    account_validation_service.ensure_no_hierarchy_loop(node_id="B", parent_id="A", parent_chain=chain)

