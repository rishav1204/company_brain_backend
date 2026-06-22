from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.finance_os.audit_explorer.read_models.audit_timeline_models import EvidenceResponse
from app.modules.finance_os.audit_explorer.security.audit_explorer_guard import require_audit_read
from app.modules.finance_os.audit_explorer.services.audit_evidence_service import get_evidence

router = APIRouter(tags=["finance-os-audit-evidence"])


@router.get("/evidence/{object_type}/{object_id}", response_model=EvidenceResponse)
def object_evidence(object_type: str, object_id: str, context=Depends(build_request_context)) -> EvidenceResponse:
    require_audit_read(context.user)
    result = get_evidence(context.org_id, object_type=object_type, object_id=object_id)
    return EvidenceResponse(
        request_id=context.request_id,
        object_type=object_type,
        object_id=object_id,
        items=result.get("materialized") or [],
        governance_items=result.get("governance") or [],
    )
