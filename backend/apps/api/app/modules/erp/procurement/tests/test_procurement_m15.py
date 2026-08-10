from app.modules.erp.procurement.services.matching_service import _pct_variance, _within_tolerance
from app.modules.erp.procurement.validators.matching_validator import ensure_invoice_approvable, ensure_overridable
from app.modules.erp.procurement.validators.budget_validator import validate_budget_available
from app.modules.erp.procurement.validators.grn_validator import validate_received_qty
from app.modules.erp.procurement.validators.po_validator import ensure_submittable
from app.modules.erp.procurement.validators.requisition_validator import ensure_submittable as pr_submittable
from app.modules.erp.procurement.workflows.pr_approval_workflow import resolve_approval_chain
from app.services.event_consumers import _handle_procurement_workflow_approval


def test_pct_variance() -> None:
    assert _pct_variance(100, 100) == 0
    assert _pct_variance(102, 100) == 2.0


def test_within_tolerance() -> None:
    assert _within_tolerance(1.5, 2) is True
    assert _within_tolerance(3, 2) is False


def test_budget_available() -> None:
    result = validate_budget_available(allocated=1000, committed=200, consumed=300, requested=400)
    assert result["sufficient"] is True
    result2 = validate_budget_available(allocated=1000, committed=200, consumed=300, requested=600)
    assert result2["sufficient"] is False


def test_pr_status_validator() -> None:
    try:
        pr_submittable("approved")
        assert False
    except ValueError:
        assert True


def test_po_status_validator() -> None:
    try:
        ensure_submittable("sent")
        assert False
    except ValueError:
        assert True


def test_grn_qty_validator() -> None:
    try:
        validate_received_qty(ordered=10, already_received=5, incoming=6)
        assert False
    except ValueError:
        assert True


def test_match_approvable() -> None:
    ensure_invoice_approvable("matched")
    try:
        ensure_invoice_approvable("exception")
        assert False
    except ValueError:
        assert True


def test_match_override_validator() -> None:
    ensure_overridable("exception")
    try:
        ensure_overridable("matched")
        assert False
    except ValueError:
        assert True


def test_approval_chain_under_50k() -> None:
    chain = resolve_approval_chain(40000)
    assert chain == ["manager"]


def test_approval_chain_over_25l() -> None:
    chain = resolve_approval_chain(3000000)
    assert chain[-1] == "cfo"


def test_procurement_workflow_unknown() -> None:
    assert _handle_procurement_workflow_approval("org", {"entity_type": "other"}) is False


def test_invoice_line_for_po_item_by_id() -> None:
    from app.modules.erp.procurement.services.matching_service import _invoice_line_for_po_item

    lines = [
        {"id": "l1", "po_item_id": "po-a", "amount": 100},
        {"id": "l2", "po_item_id": "po-b", "amount": 200},
    ]
    assert _invoice_line_for_po_item(lines, "po-b", 0)["id"] == "l2"
    assert _invoice_line_for_po_item(lines, "missing", 1) is None


def test_po_requires_grn_defaults_true_for_stock() -> None:
    from app.modules.erp.procurement.services.matching_service import _po_requires_grn

    assert _po_requires_grn({}, [{"quantity": 5}]) is True
    assert _po_requires_grn({"metadata": {"requires_grn": False}}, [{"quantity": 5}]) is True
