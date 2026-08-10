from __future__ import annotations

from app.modules.erp.inventory.engine.costing_engine import consume_fifo_layers, weighted_average_cost


def resolve_method(item_method: str | None, policy_method: str | None) -> str:
    return str(item_method or policy_method or "weighted_average").lower()


def compute_issue_cost(
    *,
    method: str,
    issue_qty: float,
    balance_qty: float,
    balance_value: float,
    weighted_avg_cost: float,
    layers: list[dict],
    standard_unit_cost: float | None = None,
) -> tuple[float, float]:
    if issue_qty <= 0:
        raise ValueError("Issue quantity must be positive")
    if method == "standard_cost":
        unit = float(standard_unit_cost or weighted_avg_cost or 0)
        if unit <= 0:
            raise ValueError("standard_unit_cost required for standard_cost valuation")
        total = round(issue_qty * unit, 2)
        return total, unit
    if method == "fifo":
        total, _ = consume_fifo_layers(layers, issue_qty)
        unit = round(total / issue_qty, 4) if issue_qty else 0
        return total, unit
    total = round(issue_qty * weighted_avg_cost, 2)
    return total, weighted_avg_cost


def apply_receipt_to_average(
    *,
    old_qty: float,
    old_value: float,
    receipt_qty: float,
    unit_cost: float,
) -> tuple[float, float, float]:
    receipt_value = round(receipt_qty * unit_cost, 2)
    new_avg, new_value = weighted_average_cost(
        old_qty=old_qty, old_value=old_value, receipt_qty=receipt_qty, receipt_value=receipt_value,
    )
    new_qty = old_qty + receipt_qty
    return new_qty, new_value, new_avg
