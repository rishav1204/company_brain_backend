from __future__ import annotations

from typing import Any

from app.modules.platform.governance.services.audit_service import audit_service
from app.modules.platform.governance.services.evidence_service import evidence_service
from app.modules.platform.governance.services.ai_trace_service import ai_trace_service


def list_governance_logs(org_id: str, **filters: Any) -> list[dict]:
    return audit_service.list_logs(org_id, **filters)


def entity_timeline(org_id: str, *, entity_type: str, entity_id: str, limit: int = 100) -> list[dict]:
    return audit_service.entity_timeline(org_id, entity_type=entity_type, entity_id=entity_id, limit=limit)


def list_governance_evidence(org_id: str, *, entity_type: str, entity_id: str) -> list[dict]:
    return evidence_service.list_for_entity(org_id, entity_type=entity_type, entity_id=entity_id)


def get_ai_trace(org_id: str, trace_id: str) -> dict | None:
    return ai_trace_service.get_trace(org_id, trace_id)
