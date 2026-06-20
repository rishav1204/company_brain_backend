from __future__ import annotations


def extract(event_type: str, payload: dict) -> dict | None:
    journal_id = payload.get("journal_id") or payload.get("journal_entry_id")
    source_id = payload.get("source_id") or payload.get("invoice_id")
    if not journal_id:
        return None
    nodes = [{"label": "Journal", "id": str(journal_id)}]
    edges = []
    if source_id:
        nodes.append({"label": "Invoice", "id": str(source_id)})
        edges.append(
            {
                "from_label": "Invoice",
                "from_id": str(source_id),
                "rel_type": "GENERATED",
                "to_label": "Journal",
                "to_id": str(journal_id),
            }
        )
    return {"nodes": nodes, "edges": edges, "entity_type": "journal", "entity_id": str(journal_id)}
