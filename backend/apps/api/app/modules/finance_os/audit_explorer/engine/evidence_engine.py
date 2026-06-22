from __future__ import annotations

from app.modules.finance_os.audit_explorer.repositories.evidence_repository import audit_evidence_repository
from app.modules.finance_os.audit_explorer.read_models import audit_read_models


def collect_evidence(org_id: str, *, object_type: str, object_id: str) -> dict:
    materialized = audit_evidence_repository.list_for_object(org_id, object_type=object_type, object_id=object_id)
    governance = audit_read_models.list_governance_evidence(org_id, entity_type=object_type, entity_id=object_id)
    return {"materialized": materialized, "governance": governance}
