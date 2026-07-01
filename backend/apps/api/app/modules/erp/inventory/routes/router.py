from fastapi import APIRouter, Depends, Query

from app.modules.erp.inventory.routes import (
    adjustment_routes,
    issue_routes,
    item_routes,
    receipt_routes,
    valuation_routes,
    warehouse_routes,
)
from app.modules.erp.inventory.security.inventory_guard import require_inventory_read
from app.modules.erp.inventory.services.inventory_service import inventory_service

erp_inventory_router = APIRouter(prefix="/erp/inventory", tags=["erp-inventory"])
erp_inventory_router.include_router(item_routes.router, prefix="/items", tags=["inventory-items"])
erp_inventory_router.include_router(warehouse_routes.router, prefix="/warehouses", tags=["inventory-warehouses"])
erp_inventory_router.include_router(receipt_routes.router, prefix="/receipts", tags=["inventory-receipts"])
erp_inventory_router.include_router(issue_routes.router, prefix="/issues", tags=["inventory-issues"])
erp_inventory_router.include_router(adjustment_routes.router, tags=["inventory-adjustments"])
erp_inventory_router.include_router(valuation_routes.router, prefix="/valuation", tags=["inventory-valuation"])


def _optional_uuid_query(value: str | None) -> str | None:
    """Treat JS undefined/null sent as query strings as absent filters."""
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized or normalized.lower() in {"undefined", "null", "none"}:
        return None
    return normalized


@erp_inventory_router.get("/balances")
def list_balances(
    context=Depends(require_inventory_read),
    warehouse_id: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=500),
) -> dict:
    items = inventory_service.list_balances(
        context.org_id,
        warehouse_id=_optional_uuid_query(warehouse_id),
        limit=limit,
    )
    return {"request_id": context.request_id, "items": items}
