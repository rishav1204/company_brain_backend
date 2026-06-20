from __future__ import annotations


def extract(event_type: str, payload: dict) -> dict | None:
    payment_id = payload.get("payment_id") or payload.get("ap_payment_id")
    invoice_id = payload.get("invoice_id")
    if not payment_id:
        return None
    nodes = [{"label": "Payment", "id": str(payment_id)}]
    edges = []
    if invoice_id:
        nodes.append({"label": "Invoice", "id": str(invoice_id)})
        edges.append(
            {
                "from_label": "Invoice",
                "from_id": str(invoice_id),
                "rel_type": "PAID_BY",
                "to_label": "Payment",
                "to_id": str(payment_id),
            }
        )
    return {"nodes": nodes, "edges": edges, "entity_type": "payment", "entity_id": str(payment_id)}
