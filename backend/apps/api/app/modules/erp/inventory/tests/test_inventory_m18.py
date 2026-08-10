from app.modules.finance_os.domain_intelligence.inventory.dead_stock_detector import detect_dead_stock
from app.modules.finance_os.domain_intelligence.inventory.stock_risk_detector import (
    classify_velocity,
    detect_stock_risk,
)
from app.modules.erp.inventory.engine.costing_engine import consume_fifo_layers, weighted_average_cost
from app.modules.erp.inventory.engine.cogs_engine import (
    build_adjustment_journal_lines,
    build_cogs_journal_lines,
    build_grni_clearing_lines,
    build_receipt_journal_lines,
)
from app.modules.erp.inventory.engine.movement_engine import check_negative_stock, transfer_quantities
from app.modules.erp.inventory.engine.valuation_engine import apply_receipt_to_average, compute_issue_cost, resolve_method
from app.modules.erp.inventory.validators.stock_validator import validate_adjustment, validate_issue, validate_receipt
from app.services.event_consumers import _handle_inventory_workflow_approval


def test_fifo_layer_consumption_blueprint_example() -> None:
    layers = [
        {"id": "l1", "remaining_quantity": 100, "unit_cost": 10, "receipt_date": "2026-01-01"},
        {"id": "l2", "remaining_quantity": 100, "unit_cost": 12, "receipt_date": "2026-01-02"},
    ]
    total, consumed = consume_fifo_layers(layers, 120)
    assert total == 1240.0
    assert len(consumed) == 2
    assert consumed[0]["quantity"] == 100
    assert consumed[1]["quantity"] == 20


def test_weighted_average_receipt() -> None:
    new_avg, new_value = weighted_average_cost(old_qty=100, old_value=1000, receipt_qty=100, receipt_value=1200)
    assert new_avg == 11.0
    assert new_value == 2200.0


def test_apply_receipt_to_average() -> None:
    qty, value, avg = apply_receipt_to_average(old_qty=50, old_value=500, receipt_qty=50, unit_cost=12)
    assert qty == 100
    assert value == 1100.0
    assert avg == 11.0


def test_compute_issue_cost_weighted_average() -> None:
    total, unit = compute_issue_cost(
        method="weighted_average",
        issue_qty=10,
        balance_qty=100,
        balance_value=1100,
        weighted_avg_cost=11,
        layers=[],
    )
    assert total == 110.0
    assert unit == 11


def test_negative_stock_block() -> None:
    try:
        check_negative_stock(qty_after=-1, rule="block")
        assert False
    except ValueError:
        assert True


def test_negative_stock_allow() -> None:
    check_negative_stock(qty_after=-1, rule="allow")


def test_negative_stock_warn() -> None:
    check_negative_stock(qty_after=-1, rule="warn")


def test_receipt_journal_lines_shape() -> None:
    lines = build_receipt_journal_lines("org", total_cost=1000, inventory_account_id="inv", grni_account_id="grni")
    assert len(lines) == 2
    assert lines[0]["debit_amount"] == 1000
    assert lines[1]["credit_amount"] == 1000


def test_cogs_journal_lines_shape() -> None:
    lines = build_cogs_journal_lines("org", total_cost=500, cogs_account_id="cogs", inventory_account_id="inv")
    assert lines[0]["debit_amount"] == 500
    assert lines[1]["credit_amount"] == 500


def test_grni_clearing_lines_shape() -> None:
    lines = build_grni_clearing_lines(
        "org",
        invoice_amount=1000,
        payable_account_id="pay",
        grni_account_id="grni",
        gst_lines=[{"account_id": "gst", "amount": 180}],
    )
    debits = sum(l["debit_amount"] for l in lines)
    credits = sum(l["credit_amount"] for l in lines)
    assert debits == credits == 1180


def test_adjustment_loss_journal() -> None:
    lines = build_adjustment_journal_lines("org", value_variance=-100, inventory_account_id="inv", loss_account_id="loss")
    assert lines[0]["debit_amount"] == 100
    assert lines[1]["credit_amount"] == 100


def test_transfer_quantities() -> None:
    out_qty, in_qty = transfer_quantities(qty=25)
    assert out_qty == -25
    assert in_qty == 25


def test_resolve_method_item_override() -> None:
    assert resolve_method("fifo", "weighted_average") == "fifo"


def test_validate_receipt() -> None:
    validate_receipt(quantity=10, unit_cost=5)
    try:
        validate_receipt(quantity=0, unit_cost=5)
        assert False
    except ValueError:
        assert True


def test_validate_issue() -> None:
    validate_issue(quantity=1)
    try:
        validate_issue(quantity=0)
        assert False
    except ValueError:
        assert True


def test_validate_adjustment() -> None:
    validate_adjustment(quantity_variance=5)
    try:
        validate_adjustment(quantity_variance=0)
        assert False
    except ValueError:
        assert True


def test_dead_stock_detector() -> None:
    movements = [
        {"item_id": "i1", "warehouse_id": "w1", "movement_date": "2025-01-01"},
        {"item_id": "i2", "warehouse_id": "w1", "movement_date": "2026-06-01"},
    ]
    dead = detect_dead_stock(movements, as_of="2026-06-18", days=90)
    assert len(dead) == 1
    assert dead[0]["item_id"] == "i1"


def test_stock_velocity_classification() -> None:
    assert classify_velocity(issue_count_30d=12, issue_count_90d=20) == "fast_moving"
    assert classify_velocity(issue_count_30d=0, issue_count_90d=0) == "non_moving"


def test_stock_risk_detector() -> None:
    risks = detect_stock_risk([{"item_id": "i1", "quantity_on_hand": 0}], reorder_days=14)
    assert risks[0]["risk"] == "stockout"


def test_inventory_workflow_unknown() -> None:
    assert _handle_inventory_workflow_approval("org", {"entity_type": "other"}) is False
