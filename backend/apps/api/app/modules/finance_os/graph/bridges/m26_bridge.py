from __future__ import annotations

from app.services.neo4j_service import neo4j_service


def annotate_workflow_bottleneck(org_id: str, *, workflow_id: str, bottleneck_stage: str) -> None:
    try:
        from app.services.graph_service import upsert_graph_event

        incident_id = f"bottleneck-{workflow_id}"
        upsert_graph_event(org_id=org_id, node_type="Incident", node_id=incident_id)
        upsert_graph_event(
            org_id=org_id,
            node_type="Workflow",
            node_id=workflow_id,
            relation="BLOCKED_BY",
            target_id=incident_id,
            to_label="Incident",
        )
        neo4j_service.upsert_node(
            "Workflow",
            workflow_id,
            {"org_id": org_id, "bottleneck_stage": bottleneck_stage},
        )
    except Exception:
        pass
