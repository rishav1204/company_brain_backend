from __future__ import annotations


def extract(event_type: str, payload: dict) -> dict | None:
    asset_id = payload.get("asset_id")
    invoice_id = payload.get("source_invoice_id") or payload.get("invoice_id")
    if not asset_id:
        return None
    nodes = [{"label": "Asset", "id": str(asset_id)}]
    edges = []
    if invoice_id:
        nodes.append({"label": "Invoice", "id": str(invoice_id)})
        edges.append(
            {
                "from_label": "Invoice",
                "from_id": str(invoice_id),
                "rel_type": "CAPITALIZED_AS",
                "to_label": "Asset",
                "to_id": str(asset_id),
            }
        )
    return {"nodes": nodes, "edges": edges, "entity_type": "asset", "entity_id": str(asset_id)}
