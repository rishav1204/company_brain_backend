from __future__ import annotations


def weighted_average_cost(*, old_qty: float, old_value: float, receipt_qty: float, receipt_value: float) -> tuple[float, float]:
    new_qty = old_qty + receipt_qty
    if new_qty <= 0:
        return 0.0, 0.0
    new_value = old_value + receipt_value
    return round(new_value / new_qty, 4), round(new_value, 2)


def consume_fifo_layers(layers: list[dict], issue_qty: float) -> tuple[float, list[dict]]:
    remaining = issue_qty
    total_cost = 0.0
    consumed: list[dict] = []
    for layer in sorted(layers, key=lambda x: str(x.get("receipt_date") or "")):
        if remaining <= 0:
            break
        avail = float(layer.get("remaining_quantity") or 0)
        if avail <= 0:
            continue
        take = min(remaining, avail)
        unit = float(layer.get("unit_cost") or 0)
        total_cost += take * unit
        consumed.append({"layer_id": layer.get("id"), "quantity": take, "unit_cost": unit})
        remaining -= take
    if remaining > 0.0001:
        raise ValueError("Insufficient FIFO layers for issue")
    return round(total_cost, 2), consumed
