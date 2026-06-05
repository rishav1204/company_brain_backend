from app.modules.erp.accounts_payable.engine.matching_engine import three_way_match


def test_three_way_match_ok() -> None:
    result = three_way_match(po_amount=1000, grn_amount=1000, invoice_amount=1000)
    assert result["matched"] is True


def test_three_way_match_escalation() -> None:
    result = three_way_match(po_amount=1000, grn_amount=1000, invoice_amount=1100, tolerance=0.01)
    assert result["requires_escalation"] is True
