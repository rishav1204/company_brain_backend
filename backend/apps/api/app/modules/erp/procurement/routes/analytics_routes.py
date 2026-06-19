from __future__ import annotations

from fastapi import APIRouter, Depends

from app.modules.erp.procurement.ai.anomaly_detector import detect_anomalies
from app.modules.erp.procurement.ai.spend_analyzer import analyze_spend
from app.modules.erp.procurement.ai.vendor_recommender import recommend_vendors
from app.modules.erp.procurement.schemas.procurement_schema import VendorRecommendRequest
from app.modules.erp.procurement.security.procurement_guard import require_procurement_read
from app.modules.erp.procurement.services.procurement_policy_service import procurement_policy_service

router = APIRouter()


@router.get("/analytics/spend")
def spend_analytics(context=Depends(require_procurement_read)) -> dict:
    return {"request_id": context.request_id, "analysis": analyze_spend(context.org_id)}


@router.get("/analytics/anomalies")
def anomaly_analytics(context=Depends(require_procurement_read)) -> dict:
    return {"request_id": context.request_id, "anomalies": detect_anomalies(context.org_id)}


@router.post("/ai/recommend-vendors")
def vendor_recommendations(request: VendorRecommendRequest, context=Depends(require_procurement_read)) -> dict:
    items = recommend_vendors(context.org_id, item_hint=request.item_hint, limit=request.limit)
    return {"request_id": context.request_id, "items": items}


@router.get("/policies")
def list_policies(context=Depends(require_procurement_read)) -> dict:
    items = procurement_policy_service.list_policies(context.org_id)
    active = procurement_policy_service.get_active(context.org_id)
    return {"request_id": context.request_id, "items": items, "active": active}
