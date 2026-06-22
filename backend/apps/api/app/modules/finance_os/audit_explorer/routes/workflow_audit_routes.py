from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.finance_os.audit_explorer.read_models.audit_timeline_models import ApprovalChainResponse
from app.modules.finance_os.audit_explorer.security.audit_explorer_guard import require_audit_read
from app.modules.finance_os.audit_explorer.services.workflow_trace_service import get_approval_chain

router = APIRouter(tags=["finance-os-audit-workflow"])


@router.get("/approval-chain/{workflow_id}", response_model=ApprovalChainResponse)
def approval_chain(workflow_id: str, context=Depends(build_request_context)) -> ApprovalChainResponse:
    require_audit_read(context.user)
    result = get_approval_chain(context.org_id, workflow_id)
    return ApprovalChainResponse(
        request_id=context.request_id,
        workflow_id=workflow_id,
        approvals=result.get("approvals") or [],
        steps=result.get("steps") or [],
        instance=result.get("instance"),
    )
