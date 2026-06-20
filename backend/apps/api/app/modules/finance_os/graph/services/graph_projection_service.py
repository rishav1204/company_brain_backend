from __future__ import annotations

from app.services.graph_extraction_service import extract_relationships_for_org
from app.modules.finance_os.graph.repositories.sync_audit_repository import sync_audit_repository


def rebuild_org(org_id: str, *, trace_id: str | None = None) -> dict:
    result = extract_relationships_for_org(org_id=org_id)
    sync_audit_repository.create(
        org_id,
        source_event_type="graph.rebuild",
        entity_type=None,
        entity_id=None,
        mutation_type="full_rescan",
        status="success",
        trace_id=trace_id,
        metadata=result,
    )
    return result
