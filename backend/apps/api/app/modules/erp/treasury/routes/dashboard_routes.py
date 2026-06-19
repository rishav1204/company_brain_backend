from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.treasury.security.treasury_guard import require_treasury_admin, require_treasury_read
from app.modules.erp.treasury.services.liquidity_service import liquidity_service

router = APIRouter()


@router.get("/alerts")
def list_alerts(context=Depends(require_treasury_read), status: str | None = Query(default="open")) -> dict:
    items = liquidity_service.list_alerts(context.org_id, status=status)
    return {"request_id": context.request_id, "items": items}


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str, context=Depends(require_treasury_admin)) -> dict:
    try:
        item = liquidity_service.acknowledge_alert(context.org_id, alert_id=alert_id, acknowledged_by=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
