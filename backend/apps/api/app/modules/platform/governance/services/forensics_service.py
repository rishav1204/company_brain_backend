from __future__ import annotations

from typing import Any

from app.modules.platform.governance.repositories.violation_repository import violation_repository
from app.modules.platform.governance.services.audit_service import audit_service
from app.modules.platform.governance.repositories.compliance_repository import compliance_repository


class ForensicsService:
    def incident_timeline(
        self,
        org_id: str,
        *,
        trace_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        audit_items = audit_service.list_logs(
            org_id,
            trace_id=trace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            limit=limit,
        )
        compliance_items: list[dict] = []
        if compliance_repository.schema_ready():
            compliance_items = compliance_repository.list_events(org_id, limit=min(limit, 100))
        violations = violation_repository.list_open(org_id, limit=50)
        return {
            "trace_id": trace_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "audit_count": len(audit_items),
            "audit_items": audit_items,
            "compliance_items": compliance_items,
            "open_violations": violations,
        }

    def rollback_analysis(self, org_id: str, *, entity_type: str, entity_id: str) -> dict[str, Any]:
        timeline = audit_service.entity_timeline(org_id, entity_type=entity_type, entity_id=entity_id, limit=500)
        states = []
        for item in reversed(timeline):
            if item.get("before_state"):
                states.append({"at": item.get("created_at"), "state": item.get("before_state")})
            if item.get("after_state"):
                states.append({"at": item.get("created_at"), "state": item.get("after_state")})
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "state_chain": states,
            "can_reconstruct": len(states) > 0,
        }


forensics_service = ForensicsService()
