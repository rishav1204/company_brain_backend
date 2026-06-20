from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.finance_os.workflow_intelligence.ai.workflow_copilot import WorkflowCopilot
from app.modules.finance_os.workflow_intelligence.ai.workflow_reasoner import build_reasoning_context
from app.modules.finance_os.workflow_intelligence.pipelines.workflow_intelligence_pipeline import workflow_intelligence_pipeline
from app.modules.finance_os.workflow_intelligence.schemas.workflow_intelligence_schema import AnalyzeRequest, CopilotRequest, HealthResponse
from app.modules.finance_os.workflow_intelligence.security.workflow_intelligence_guard import (
    require_workflow_intelligence_read,
    require_workflow_intelligence_write,
)
from app.modules.finance_os.workflow_intelligence.services.bottleneck_service import bottleneck_service
from app.modules.finance_os.workflow_intelligence.services.workflow_analysis_service import workflow_analysis_service
from app.modules.finance_os.workflow_intelligence.services.workflow_insight_service import workflow_insight_service

router = APIRouter(tags=["finance-os-workflow-intelligence"])


@router.get("/health", response_model=HealthResponse)
def get_health(context=Depends(build_request_context)) -> HealthResponse:
    require_workflow_intelligence_read(context.user)
    h = workflow_insight_service.health(str(context.org_id))
    return HealthResponse(**h)


@router.post("/analyze")
def analyze(body: AnalyzeRequest, context=Depends(build_request_context)) -> dict:
    require_workflow_intelligence_write(context.user)
    return workflow_intelligence_pipeline.run(
        str(context.org_id),
        workflow_instance_id=body.workflow_instance_id,
        workflow_type=body.workflow_type,
    )


@router.post("/copilot")
def copilot(body: CopilotRequest, context=Depends(build_request_context)) -> dict:
    require_workflow_intelligence_read(context.user)
    org_id = str(context.org_id)
    snap = None
    if body.workflow_instance_id:
        snap = workflow_analysis_service.get_snapshot(org_id, body.workflow_instance_id)
    bottlenecks = bottleneck_service.list_bottlenecks(org_id, workflow_type=body.workflow_type)
    ctx = build_reasoning_context(
        snapshot=snap,
        stage_metrics=[],
        bottlenecks=bottlenecks,
        predictions=[],
        recommendations=[],
    )
    answer = WorkflowCopilot().answer(org_id, question=body.question, context=ctx)
    return {"answer": answer}


@router.get("/snapshots/{workflow_instance_id}")
def get_snapshot(workflow_instance_id: str, context=Depends(build_request_context)) -> dict:
    require_workflow_intelligence_read(context.user)
    row = workflow_analysis_service.get_snapshot(str(context.org_id), workflow_instance_id)
    return row or {}
