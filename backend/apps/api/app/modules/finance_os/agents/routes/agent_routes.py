from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import build_request_context
from app.modules.finance_os.agents.orchestrator.agent_registry import AGENT_CATALOG
from app.modules.finance_os.agents.orchestrator.workflow_launcher import workflow_launcher
from app.modules.finance_os.agents.pipelines.agent_orchestration_pipeline import agent_orchestration_pipeline
from app.modules.finance_os.agents.repositories.execution_repository import execution_repository
from app.modules.finance_os.agents.repositories.recommendation_repository import recommendation_repository
from app.modules.finance_os.agents.schemas.api_schema import FinanceAgentRunRequest, FinanceAgentRunResponse, WorkflowLaunchRequest
from app.modules.finance_os.agents.security.agents_guard import require_agent_read, require_agent_run
from app.services.repositories import audit_repo

router = APIRouter(tags=["finance-os-agents"])


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "module": "finance_os.agents",
        "schema_ready": execution_repository.schema_ready(),
    }


@router.get("/catalog")
def catalog(context=Depends(build_request_context)) -> dict:
    require_agent_read(context.user)
    return {"agents": AGENT_CATALOG}


@router.post("/run", response_model=FinanceAgentRunResponse)
def run_agent(request: FinanceAgentRunRequest, context=Depends(build_request_context)) -> FinanceAgentRunResponse:
    require_agent_run(context.user)
    try:
        result = agent_orchestration_pipeline.run(
            context.org_id,
            request.agent_type,
            request.trigger_type,
            request.payload,
            trace_id=context.request_id,
            principal_roles=context.roles,
            principal_attrs=context.attrs,
            user_id=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FinanceAgentRunResponse(**{k: result[k] for k in FinanceAgentRunResponse.model_fields if k in result})


@router.get("/executions")
def list_executions(
    agent_name: str | None = None,
    status: str | None = None,
    context=Depends(build_request_context),
) -> dict:
    require_agent_read(context.user)
    items = execution_repository.list(context.org_id, agent_name=agent_name, status=status)
    return {"items": items, "count": len(items)}


@router.get("/executions/{execution_id}")
def get_execution(execution_id: str, context=Depends(build_request_context)) -> dict:
    require_agent_read(context.user)
    row = execution_repository.get(context.org_id, execution_id)
    if not row:
        raise HTTPException(status_code=404, detail="Execution not found")
    recs = recommendation_repository.list_for_execution(context.org_id, execution_id)
    return {"execution": row, "recommendations": recs}


@router.get("/recommendations")
def list_recommendations(
    status: str | None = None,
    agent_name: str | None = None,
    context=Depends(build_request_context),
) -> dict:
    require_agent_read(context.user)
    items = recommendation_repository.list(context.org_id, status=status, agent_name=agent_name)
    return {"items": items, "count": len(items)}


@router.get("/recommendations/{recommendation_id}")
def get_recommendation(recommendation_id: str, context=Depends(build_request_context)) -> dict:
    require_agent_read(context.user)
    row = recommendation_repository.get(context.org_id, recommendation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return {"recommendation": row}


@router.get("/status")
def agent_status(context=Depends(build_request_context)) -> dict:
    require_agent_read(context.user)
    return execution_repository.summary(context.org_id)


@router.post("/workflow")
def launch_workflow(request: WorkflowLaunchRequest, context=Depends(build_request_context)) -> dict:
    require_agent_run(context.user)
    rec = recommendation_repository.get(context.org_id, request.recommendation_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    workflow_key = request.workflow_key or (rec.get("metadata") or {}).get("plan", {}).get("workflow_key")
    if not workflow_key:
        raise HTTPException(status_code=400, detail="workflow_key required")
    wf = workflow_launcher.launch(
        context.org_id,
        workflow_key=workflow_key,
        user_id=context.user_id,
        metadata={"recommendation_id": request.recommendation_id},
        trace_id=context.request_id,
    )
    if not wf:
        raise HTTPException(status_code=503, detail="Workflow engine unavailable")
    recommendation_repository.update_status(
        context.org_id,
        request.recommendation_id,
        status="approved",
        workflow_instance_id=str(wf.get("workflow_id") or wf.get("id") or ""),
    )
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="agent.workflow.launched",
        object_ref=f"recommendation:{request.recommendation_id}",
        payload_jsonb={"workflow_key": workflow_key},
    )
    return {"workflow": wf}
