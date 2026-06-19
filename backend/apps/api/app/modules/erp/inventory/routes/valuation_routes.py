from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.inventory.schemas.inventory_schema import InventoryAnalyzeRequest, ValuationRunRequest
from app.modules.erp.inventory.security.inventory_guard import require_inventory_read, require_inventory_value
from app.modules.erp.inventory.services.movement_service import movement_service
from app.modules.erp.inventory.services.valuation_service import valuation_service

router = APIRouter()


@router.get("/movements")
def list_movements(
    context=Depends(require_inventory_read),
    item_id: str | None = Query(default=None),
    warehouse_id: str | None = Query(default=None),
) -> dict:
    items = movement_service.list_movements(context.org_id, item_id=item_id, warehouse_id=warehouse_id)
    return {"request_id": context.request_id, "items": items}


@router.get("")
def list_valuations(
    context=Depends(require_inventory_read),
    valuation_date: str | None = Query(default=None),
) -> dict:
    items = valuation_service.list_snapshots(context.org_id, valuation_date=valuation_date)
    return {"request_id": context.request_id, "items": items}


@router.post("/run")
def run_valuation(request: ValuationRunRequest, context=Depends(require_inventory_value)) -> dict:
    try:
        items = valuation_service.run_snapshot(context.org_id, valuation_date=request.valuation_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "items": items}


@router.post("/ai/analyze")
def analyze_inventory(request: InventoryAnalyzeRequest, context=Depends(require_inventory_read)) -> dict:
    from app.modules.erp.inventory.ai.inventory_analyzer import analyze

    result = analyze(context.org_id, query=request.query)
    return {"request_id": context.request_id, "analysis": result}
