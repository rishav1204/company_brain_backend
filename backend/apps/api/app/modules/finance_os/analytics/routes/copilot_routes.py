from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.finance_os.analytics.ai.executive_copilot import answer
from app.modules.finance_os.analytics.schemas.analytics_schema import CopilotRequest, CopilotResponse
from app.modules.finance_os.analytics.security.analytics_guard import require_analytics_read, require_analytics_refresh
from app.modules.finance_os.analytics.pipelines.analytics_refresh_pipeline import run_refresh
from app.services.repositories import audit_repo

router = APIRouter(tags=["finance-os-analytics-copilot"])


@router.post("/copilot/ask", response_model=CopilotResponse)
def copilot_ask(body: CopilotRequest, context=Depends(build_request_context)) -> CopilotResponse:
    require_analytics_read(context.user)
    result = answer(context.org_id, body.question)
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="analytics.copilot.asked",
        object_ref="finance_os:analytics:copilot",
        payload_jsonb={"question": body.question},
    )
    return CopilotResponse(**result)


@router.post("/refresh")
def refresh_analytics(context=Depends(build_request_context)) -> dict:
    require_analytics_refresh(context.user)
    result = run_refresh(context.org_id)
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="analytics.kpi.calculated",
        object_ref="finance_os:analytics:refresh",
        payload_jsonb=result if isinstance(result, dict) else {"result": result},
    )
    return {"request_id": context.request_id, "result": result}
