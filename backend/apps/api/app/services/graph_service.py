from app.services.neo4j_service import neo4j_service
from app.services.repositories import graph_data_repo

_RELATION_TARGET_LABELS = {
    "ISSUED": "Invoice",
    "REQUIRES_APPROVAL": "Workflow",
    "PAID_BY": "Payment",
    "RELATES_TO": "Invoice",
    "REFERENCES": "Vendor",
    "GOVERNS": "Vendor",
    "APPROVES": "Invoice",
    "ASSIGNED_TO": "Workflow",
    "BLOCKED_BY": "Workflow",
    "IMPACTS": "KPI",
}


def _resolve_to_label(relation: str | None, from_label: str) -> str:
    if relation == "BLOCKED_BY" and from_label == "Incident":
        return "Workflow"
    if relation == "IMPACTS" and from_label == "Decision":
        return "KPI"
    if relation == "RELATES_TO" and from_label == "PurchaseOrder":
        return "Invoice"
    if relation == "PAID_BY" and from_label == "Invoice":
        return "Payment"
    if relation == "GOVERNS" and from_label == "Contract":
        return "Vendor"
    if relation == "APPROVES" and from_label == "User":
        return "Invoice"
    return _RELATION_TARGET_LABELS.get(relation or "", "Workflow")


def query_related_entities(org_id: str, subject_ref: str | None) -> list[str]:
    if not subject_ref:
        return []
    related = []
    workflow_ids = graph_data_repo.list_workflow_ids(org_id=org_id)
    invoice_ids = graph_data_repo.list_invoice_ids(org_id=org_id)
    if subject_ref in workflow_ids:
        related.append(f"Workflow:{subject_ref} -> BLOCKED_BY -> Incident:intercompany-mismatch")
    if subject_ref in invoice_ids:
        related.append(f"Invoice:{subject_ref} -> REQUIRES_APPROVAL -> User:finance-manager")
    neo4j_related = neo4j_service.query_related(org_id=org_id, subject_id=subject_ref)
    return related + neo4j_related


def upsert_graph_event(
    org_id: str,
    node_type: str,
    node_id: str,
    relation: str | None = None,
    target_id: str | None = None,
    to_label: str | None = None,
) -> dict:
    result = neo4j_service.upsert_node(
        label=node_type,
        node_id=node_id,
        properties={"org_id": org_id, "updated_by": "graph_service"},
    )
    relationship_result = None
    if relation and target_id:
        resolved_to_label = to_label or _resolve_to_label(relation, node_type)
        relationship_result = neo4j_service.upsert_relationship(
            org_id=org_id,
            from_label=node_type,
            from_id=node_id,
            rel_type=relation,
            to_label=resolved_to_label,
            to_id=target_id,
        )
    return {
        "org_id": org_id,
        "node_type": node_type,
        "node_id": node_id,
        "relation": relation,
        "target_id": target_id,
        "status": result.get("status", "upserted"),
        "relationship_status": relationship_result.get("status") if isinstance(relationship_result, dict) else None,
    }
