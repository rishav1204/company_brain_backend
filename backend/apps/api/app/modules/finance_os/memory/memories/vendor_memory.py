from __future__ import annotations

from app.modules.finance_os.memory.engine.importance_engine import compute_importance


def extract(event_type: str, payload: dict) -> dict | None:
    vendor_id = payload.get("vendor_id") or payload.get("vendorId")
    vendor_name = payload.get("vendor_name") or payload.get("vendorName") or "Vendor"
    amount = _amount(payload)
    if event_type in {"payment.executed", "erp.payment.completed"}:
        days_late = payload.get("days_late") or payload.get("payment_delay_days")
        content = f"{vendor_name} payment executed"
        if amount:
            content += f" for ₹{amount:,.0f}"
        if days_late is not None:
            content += f"; typically {days_late} days from due date"
        return {
            "memory_type": "vendor",
            "entity_type": "vendor",
            "entity_id": str(vendor_id) if vendor_id else None,
            "title": f"{vendor_name} payment behavior",
            "content": content,
            "importance_score": compute_importance(event_type=event_type, amount=amount),
            "references": [{"source_type": "payment", "source_id": payload.get("payment_id")}],
            "ttl_policy": "180d",
        }
    if event_type in {"invoice.duplicate_detected", "invoice.anomaly_detected"}:
        return {
            "memory_type": "vendor",
            "entity_type": "vendor",
            "entity_id": str(vendor_id) if vendor_id else None,
            "title": f"{vendor_name} invoice risk",
            "content": f"Invoice risk flagged for {vendor_name}: {payload.get('reason', event_type)}",
            "importance_score": compute_importance(
                event_type=event_type,
                amount=amount,
                anomaly=event_type.endswith("anomaly_detected"),
                duplicate=event_type.endswith("duplicate_detected"),
            ),
            "references": [{"source_type": "invoice", "source_id": payload.get("invoice_id")}],
            "ttl_policy": "180d",
        }
    if event_type == "erp.invoice.approved" and amount and amount >= 50_000:
        return {
            "memory_type": "vendor",
            "entity_type": "vendor",
            "entity_id": str(vendor_id) if vendor_id else None,
            "title": f"{vendor_name} approval pattern",
            "content": f"{vendor_name} invoices around ₹{amount:,.0f} approved routinely",
            "importance_score": compute_importance(event_type=event_type, amount=amount),
            "references": [{"source_type": "ap_invoice", "source_id": payload.get("invoice_id")}],
            "ttl_policy": "90d",
        }
    return None


def _amount(payload: dict) -> float | None:
    for key in ("amount", "total_amount", "payment_amount", "grand_total"):
        raw = payload.get(key)
        if raw is not None:
            try:
                return float(raw)
            except (TypeError, ValueError):
                pass
    return None
