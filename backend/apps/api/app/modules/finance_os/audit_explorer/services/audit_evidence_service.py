from __future__ import annotations

from app.modules.finance_os.audit_explorer.engine.evidence_engine import collect_evidence


def get_evidence(org_id: str, *, object_type: str, object_id: str) -> dict:
    return collect_evidence(org_id, object_type=object_type, object_id=object_id)
