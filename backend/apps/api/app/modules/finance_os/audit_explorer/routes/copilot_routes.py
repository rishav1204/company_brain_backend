from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.finance_os.audit_explorer.ai.audit_copilot import answer
from app.modules.finance_os.audit_explorer.read_models.audit_timeline_models import CopilotRequest, CopilotResponse
from app.modules.finance_os.audit_explorer.security.audit_explorer_guard import require_audit_copilot, require_audit_refresh
from app.modules.finance_os.audit_explorer.pipelines.audit_materialization_pipeline import run_refresh_object
from app.modules.platform.governance.services.audit_service import audit_service

router = APIRouter(tags=["finance-os-audit-copilot"])


@router.post("/copilot/ask", response_model=CopilotResponse)
def copilot_ask(body: CopilotRequest, context=Depends(build_request_context)) -> CopilotResponse:
    require_audit_copilot(context.user)
    result = answer(context.org_id, body.question, object_type=body.object_type, object_id=body.object_id)
    audit_service.record(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        action="audit.copilot.ask",
        object_ref="finance_os:audit:copilot",
        payload={"question": body.question[:500], "object_type": body.object_type, "object_id": body.object_id},
        source_service="finance_os.audit_explorer",
    )
    return CopilotResponse(**result)


@router.post("/refresh/{object_type}/{object_id}")
def refresh_object(object_type: str, object_id: str, context=Depends(build_request_context)) -> dict:
    require_audit_refresh(context.user)
    result = run_refresh_object(context.org_id, object_type=object_type, object_id=object_id)
    audit_service.record(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        action="audit.explorer.refresh",
        object_ref=f"erp:{object_type}:{object_id}",
        payload={"object_type": object_type, "object_id": object_id},
        entity_type=object_type,
        entity_id=object_id,
        source_service="finance_os.audit_explorer",
    )
    return {"request_id": context.request_id, "result": result}
