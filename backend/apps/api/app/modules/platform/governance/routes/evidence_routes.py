from fastapi import APIRouter, Depends, Query

from app.modules.platform.governance.api.deps import require_auditor_read, require_governance_write
from app.modules.platform.governance.services.ai_trace_service import ai_trace_service
from app.modules.platform.governance.services.evidence_service import evidence_service
from pydantic import BaseModel, Field

router = APIRouter(tags=["governance-evidence"])


class EvidenceLinkRequest(BaseModel):
    entity_type: str
    entity_id: str
    evidence_type: str
    evidence_ref: str
    metadata: dict = Field(default_factory=dict)


class AITraceRequest(BaseModel):
    prompt: str
    reasoning_summary: str
    confidence_score: float | None = None
    decision: dict = Field(default_factory=dict)
    workflow_id: str | None = None
    agent_run_id: str | None = None


@router.get("/audit/evidence/{entity_type}/{entity_id}")
def list_evidence(entity_type: str, entity_id: str, context=Depends(require_auditor_read)) -> dict:
    items = evidence_service.list_for_entity(context.org_id, entity_type=entity_type, entity_id=entity_id)
    return {"request_id": context.request_id, "items": items}


@router.post("/audit/evidence/link")
def link_evidence(request: EvidenceLinkRequest, context=Depends(require_governance_write)) -> dict:
    row = evidence_service.link(context.org_id, **request.model_dump())
    return {"request_id": context.request_id, "link": row}


@router.post("/audit/ai-traces")
def record_ai_trace(request: AITraceRequest, context=Depends(require_governance_write)) -> dict:
    row = ai_trace_service.record_reasoning(context.org_id, **request.model_dump())
    return {"request_id": context.request_id, "trace": row}


@router.get("/audit/ai-traces/{trace_id}")
def get_ai_trace(trace_id: str, context=Depends(require_auditor_read)) -> dict:
    row = ai_trace_service.get_trace(context.org_id, trace_id)
    return {"request_id": context.request_id, "trace": row}
