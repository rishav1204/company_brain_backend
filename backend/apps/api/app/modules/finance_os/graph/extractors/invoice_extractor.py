from __future__ import annotations


def extract(event_type: str, payload: dict) -> dict | None:
    invoice_id = payload.get("invoice_id") or payload.get("ap_invoice_id")
    vendor_id = payload.get("vendor_id")
    if not invoice_id:
        return None
    nodes = [{"label": "Invoice", "id": str(invoice_id)}]
    edges = []
    if vendor_id:
        nodes.append({"label": "Vendor", "id": str(vendor_id)})
        edges.append(
            {
                "from_label": "Vendor",
                "from_id": str(vendor_id),
                "rel_type": "ISSUED",
                "to_label": "Invoice",
                "to_id": str(invoice_id),
            }
        )
    workflow_id = payload.get("workflow_id") or payload.get("workflow_instance_id")
    if workflow_id and event_type in {"approval.requested", "erp.invoice.approved"}:
        nodes.append({"label": "Workflow", "id": str(workflow_id)})
        edges.append(
            {
                "from_label": "Invoice",
                "from_id": str(invoice_id),
                "rel_type": "REQUIRES_APPROVAL",
                "to_label": "Workflow",
                "to_id": str(workflow_id),
            }
        )
    if event_type == "invoice.anomaly_detected":
        incident_id = payload.get("incident_id") or f"anomaly-{invoice_id}"
        nodes.append({"label": "Incident", "id": str(incident_id)})
        edges.append(
            {
                "from_label": "Invoice",
                "from_id": str(invoice_id),
                "rel_type": "RELATED_TO",
                "to_label": "Incident",
                "to_id": str(incident_id),
            }
        )
    return {"nodes": nodes, "edges": edges, "entity_type": "invoice", "entity_id": str(invoice_id)}
