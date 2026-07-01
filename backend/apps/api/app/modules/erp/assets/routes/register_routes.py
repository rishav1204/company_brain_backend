from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.modules.erp.assets.ai.anomaly_detector import detect_anomalies
from app.modules.erp.assets.ai.asset_copilot import suggest
from app.modules.erp.assets.schemas.asset_schema import CandidateConvertRequest, CopilotSuggestRequest
from app.modules.erp.assets.security.asset_guard import require_asset_create, require_asset_read
from app.modules.erp.assets.services.asset_service import asset_service
from app.modules.erp.assets.services.candidate_service import candidate_service

router = APIRouter()


@router.get("/candidates")
def list_candidates(context=Depends(require_asset_read), status: str | None = Query(default=None)) -> dict:
    items = candidate_service.list(context.org_id, status=status)
    return {"request_id": context.request_id, "items": items}


@router.post("/candidates/{candidate_id}/convert")
def convert_candidate(
    candidate_id: str,
    request: CandidateConvertRequest,
    context=Depends(require_asset_create),
) -> dict:
    item = candidate_service.convert(
        context.org_id,
        candidate_id=candidate_id,
        actor_id=context.user_id,
        asset_name=request.asset_name,
    )
    return {"request_id": context.request_id, "item": item}


@router.post("/ai/suggest")
def ai_suggest(request: CopilotSuggestRequest, context=Depends(require_asset_read)) -> dict:
    return {"request_id": context.request_id, "suggestion": suggest(request.description, request.amount)}


@router.get("/analytics/anomalies")
def anomalies(context=Depends(require_asset_read)) -> dict:
    assets = asset_service.list(context.org_id)
    items = detect_anomalies(assets)
    return {"request_id": context.request_id, "items": items}
