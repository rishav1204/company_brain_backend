from __future__ import annotations

from uuid import uuid4


def allocate_partial(*, invoice_amount: float, payment_amount: float) -> dict:
    invoice_amount = max(0.0, float(invoice_amount))
    payment_amount = max(0.0, float(payment_amount))
    allocated = min(invoice_amount, payment_amount)
    remaining = max(0.0, invoice_amount - allocated)
    status = "matched" if remaining < 0.05 else "partially_matched"
    return {
        "allocated_amount": round(allocated, 2),
        "remaining_amount": round(remaining, 2),
        "status": status,
    }


def build_match_lines(
    *,
    reconciliation_id: str,
    bank_transaction_id: str | None,
    allocations: list[dict],
    match_group_id: str | None = None,
) -> list[dict]:
    group = match_group_id or str(uuid4())
    lines: list[dict] = []
    for alloc in allocations:
        entity_type = str(alloc.get("entity_type") or "")
        entity_id = str(alloc.get("entity_id") or "")
        amount = float(alloc.get("amount") or 0)
        invoice_total = float(alloc.get("invoice_amount") or amount)
        partial = allocate_partial(invoice_amount=invoice_total, payment_amount=amount)
        lines.append({
            "reconciliation_id": reconciliation_id,
            "bank_transaction_id": alloc.get("bank_transaction_id") or bank_transaction_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "allocated_amount": partial["allocated_amount"],
            "remaining_amount": partial["remaining_amount"],
            "match_group_id": group,
            "metadata": alloc.get("metadata") or {},
        })
    return lines


def group_status(lines: list[dict]) -> str:
    if not lines:
        return "matched"
    if any(float(l.get("remaining_amount") or 0) > 0.05 for l in lines):
        return "partially_matched"
    return "matched"
