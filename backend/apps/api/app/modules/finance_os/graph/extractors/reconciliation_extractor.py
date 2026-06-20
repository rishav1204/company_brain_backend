from __future__ import annotations


def extract(event_type: str, payload: dict) -> dict | None:
    recon_id = payload.get("reconciliation_id") or payload.get("bank_reconciliation_id")
    bank_tx_id = payload.get("bank_transaction_id") or payload.get("transaction_id")
    if not recon_id and not bank_tx_id:
        return None
    nodes = []
    edges = []
    if recon_id:
        nodes.append({"label": "Reconciliation", "id": str(recon_id)})
    if bank_tx_id:
        nodes.append({"label": "BankTransaction", "id": str(bank_tx_id)})
        if recon_id:
            edges.append(
                {
                    "from_label": "BankTransaction",
                    "from_id": str(bank_tx_id),
                    "rel_type": "MATCHED_IN",
                    "to_label": "Reconciliation",
                    "to_id": str(recon_id),
                }
            )
    entity_id = str(recon_id or bank_tx_id)
    return {"nodes": nodes, "edges": edges, "entity_type": "reconciliation", "entity_id": entity_id}
