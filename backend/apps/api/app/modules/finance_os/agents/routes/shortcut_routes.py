from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.finance_os.agents.pipelines.agent_orchestration_pipeline import agent_orchestration_pipeline
from app.modules.finance_os.agents.schemas.api_schema import FinanceAgentRunRequest, FinanceAgentRunResponse
from app.modules.finance_os.agents.security.agents_guard import require_agent_run

router = APIRouter(tags=["finance-os-agents-shortcuts"])


def _shortcut(agent_type: str, request: FinanceAgentRunRequest, context) -> FinanceAgentRunResponse:
    require_agent_run(context.user)
    payload = {**request.payload, "task_type": request.payload.get("task_type")}
    result = agent_orchestration_pipeline.run(
        context.org_id,
        agent_type,
        request.trigger_type,
        payload,
        trace_id=context.request_id,
        principal_roles=context.roles,
        principal_attrs=context.attrs,
        user_id=context.user_id,
    )
    return FinanceAgentRunResponse(**{k: result[k] for k in FinanceAgentRunResponse.model_fields if k in result})


@router.post("/ap/run", response_model=FinanceAgentRunResponse)
def run_ap(request: FinanceAgentRunRequest, context=Depends(build_request_context)) -> FinanceAgentRunResponse:
    return _shortcut("ap_agent", request, context)


@router.post("/reconciliation/run", response_model=FinanceAgentRunResponse)
def run_reconciliation(request: FinanceAgentRunRequest, context=Depends(build_request_context)) -> FinanceAgentRunResponse:
    return _shortcut("reconciliation_agent", request, context)


@router.post("/gst/run", response_model=FinanceAgentRunResponse)
def run_gst(request: FinanceAgentRunRequest, context=Depends(build_request_context)) -> FinanceAgentRunResponse:
    return _shortcut("gst_agent", request, context)


@router.post("/close/run", response_model=FinanceAgentRunResponse)
def run_close(request: FinanceAgentRunRequest, context=Depends(build_request_context)) -> FinanceAgentRunResponse:
    return _shortcut("close_agent", request, context)


@router.post("/collections/run", response_model=FinanceAgentRunResponse)
def run_collections(request: FinanceAgentRunRequest, context=Depends(build_request_context)) -> FinanceAgentRunResponse:
    return _shortcut("collections_agent", request, context)
