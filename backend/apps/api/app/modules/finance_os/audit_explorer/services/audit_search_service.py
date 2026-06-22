from __future__ import annotations

from app.modules.finance_os.audit_explorer.repositories.timeline_repository import timeline_repository
from app.modules.finance_os.audit_explorer.read_models import audit_read_models


def search(
    org_id: str,
    *,
    q: str | None = None,
    object_type: str | None = None,
    actor_id: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    items = timeline_repository.search(
        org_id,
        q=q,
        object_type=object_type,
        actor_id=actor_id,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    if not items and q:
        logs = audit_read_models.list_governance_logs(org_id, limit=limit, offset=offset)
        pattern = q.lower()
        items = [
            {
                "id": row.get("id"),
                "object_type": row.get("entity_type"),
                "object_id": row.get("entity_id"),
                "event_type": row.get("event_type") or row.get("action"),
                "actor_id": row.get("actor_id"),
                "event_timestamp": row.get("created_at"),
                "metadata": row.get("payload_jsonb") or {},
                "object_ref": row.get("object_ref"),
                "source": "governance_audit_logs",
            }
            for row in logs
            if pattern in str(row).lower()
        ]
    return items
