from __future__ import annotations


def extract(event_type: str, payload: dict) -> dict | None:
    workflow_id = payload.get("workflow_id") or payload.get("workflow_instance_id")
    if not workflow_id:
        return None
    nodes = [{"label": "Workflow", "id": str(workflow_id)}]
    edges = []
    approver_id = payload.get("approver_id") or payload.get("assignee_id") or payload.get("approved_by")
    object_id = payload.get("object_id") or payload.get("invoice_id")
    if event_type in {"approval.completed", "approval.rejected"} and approver_id and object_id:
        nodes.append({"label": "User", "id": str(approver_id)})
        nodes.append({"label": "Invoice", "id": str(object_id)})
        edges.append(
            {
                "from_label": "User",
                "from_id": str(approver_id),
                "rel_type": "APPROVES",
                "to_label": "Invoice",
                "to_id": str(object_id),
            }
        )
    if event_type in {"workflow.failed", "sla.breached"}:
        incident_id = payload.get("incident_id") or f"incident-{workflow_id}"
        nodes.append({"label": "Incident", "id": str(incident_id)})
        edges.append(
            {
                "from_label": "Workflow",
                "from_id": str(workflow_id),
                "rel_type": "BLOCKED_BY",
                "to_label": "Incident",
                "to_id": str(incident_id),
            }
        )
    prior_wf = payload.get("prior_workflow_id")
    if prior_wf and event_type == "workflow.completed":
        nodes.append({"label": "Workflow", "id": str(prior_wf)})
        edges.append(
            {
                "from_label": "Workflow",
                "from_id": str(prior_wf),
                "rel_type": "PRECEDES",
                "to_label": "Workflow",
                "to_id": str(workflow_id),
            }
        )
    return {"nodes": nodes, "edges": edges, "entity_type": "workflow", "entity_id": str(workflow_id)}
