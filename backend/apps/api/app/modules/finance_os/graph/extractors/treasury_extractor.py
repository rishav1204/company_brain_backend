from __future__ import annotations


def extract(event_type: str, payload: dict) -> dict | None:
    payment_id = payload.get("payment_id")
    bank_tx_id = payload.get("bank_transaction_id") or payload.get("transaction_id")
    if event_type in {"bank.transaction.imported", "bank.statement.imported"} and bank_tx_id:
        nodes = [{"label": "BankTransaction", "id": str(bank_tx_id)}]
        edges = []
        if payment_id:
            nodes.append({"label": "Payment", "id": str(payment_id)})
            edges.append(
                {
                    "from_label": "Payment",
                    "from_id": str(payment_id),
                    "rel_type": "SETTLED_BY",
                    "to_label": "BankTransaction",
                    "to_id": str(bank_tx_id),
                }
            )
        return {"nodes": nodes, "edges": edges, "entity_type": "bank_transaction", "entity_id": str(bank_tx_id)}
    if event_type == "liquidity_alert.created":
        alert_id = payload.get("alert_id") or payload.get("id") or "liquidity-alert"
        return {
            "nodes": [{"label": "Incident", "id": str(alert_id)}],
            "edges": [],
            "entity_type": "treasury",
            "entity_id": str(alert_id),
        }
    return None
