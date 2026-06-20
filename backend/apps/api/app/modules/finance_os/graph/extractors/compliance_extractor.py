from __future__ import annotations


def extract(event_type: str, payload: dict) -> dict | None:
    gst_return_id = payload.get("gst_return_id") or payload.get("return_id")
    invoice_id = payload.get("invoice_id") or payload.get("source_id")
    compliance_id = payload.get("compliance_id") or payload.get("filing_id")
    nodes = []
    edges = []
    if gst_return_id:
        nodes.append({"label": "GSTReturn", "id": str(gst_return_id)})
    if invoice_id and gst_return_id:
        nodes.append({"label": "Invoice", "id": str(invoice_id)})
        edges.append(
            {
                "from_label": "Invoice",
                "from_id": str(invoice_id),
                "rel_type": "REPORTED_IN",
                "to_label": "GSTReturn",
                "to_id": str(gst_return_id),
            }
        )
    if compliance_id and gst_return_id:
        nodes.append({"label": "Compliance", "id": str(compliance_id)})
        edges.append(
            {
                "from_label": "GSTReturn",
                "from_id": str(gst_return_id),
                "rel_type": "FILED_AS",
                "to_label": "Compliance",
                "to_id": str(compliance_id),
            }
        )
    if not nodes:
        return None
    entity_id = str(gst_return_id or compliance_id or invoice_id)
    return {"nodes": nodes, "edges": edges, "entity_type": "compliance", "entity_id": entity_id}
