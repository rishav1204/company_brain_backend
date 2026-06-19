from __future__ import annotations

from app.modules.erp.inventory.engine.costing_engine import consume_fifo_layers
from app.modules.erp.inventory.engine.valuation_engine import apply_receipt_to_average, compute_issue_cost, resolve_method


class CostingService:
    def receipt_cost(self, *, qty: float, unit_cost: float) -> float:
        return round(qty * unit_cost, 2)

    def issue_cost(
        self,
        *,
        method: str,
        issue_qty: float,
        balance: dict,
        layers: list[dict],
    ) -> tuple[float, float, list[dict]]:
        m = resolve_method(method, None)
        total, unit = compute_issue_cost(
            method=m,
            issue_qty=issue_qty,
            balance_qty=float(balance.get("quantity_on_hand") or 0),
            balance_value=float(balance.get("inventory_value") or 0),
            weighted_avg_cost=float(balance.get("weighted_avg_cost") or 0),
            layers=layers,
        )
        consumed: list[dict] = []
        if m == "fifo":
            _, consumed = consume_fifo_layers(layers, issue_qty)
        return total, unit, consumed

    def receipt_average(
        self,
        *,
        balance: dict,
        receipt_qty: float,
        unit_cost: float,
    ) -> tuple[float, float, float]:
        return apply_receipt_to_average(
            old_qty=float(balance.get("quantity_on_hand") or 0),
            old_value=float(balance.get("inventory_value") or 0),
            receipt_qty=receipt_qty,
            unit_cost=unit_cost,
        )


costing_service = CostingService()
