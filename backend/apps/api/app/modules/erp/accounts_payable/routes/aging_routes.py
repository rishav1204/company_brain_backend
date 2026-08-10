from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository
from app.modules.erp.accounts_payable.security.ap_guard import require_ap_read
from app.modules.erp.accounts_payable.services.aging_service import aging_service
from app.modules.erp.accounts_payable.services.vendor_balance_service import vendor_balance_service
from app.modules.erp.ports.intelligence_registry import intelligence_registry

router = APIRouter()


@router.get("/aging")
def aging_report(context=Depends(require_ap_read), as_of_date: str | None = Query(default=None)) -> dict:
    item = aging_service.report(context.org_id, as_of_date=as_of_date)
    return {"request_id": context.request_id, "item": item}


@router.get("/aging/cashflow-forecast")
def cashflow_forecast(context=Depends(require_ap_read), horizon_days: int = Query(default=30, ge=1, le=365)) -> dict:
    outstanding = invoice_repository.list_outstanding(context.org_id)
    item = intelligence_registry.ap_risk().forecast_cash_requirement(outstanding, horizon_days=horizon_days)
    return {"request_id": context.request_id, "item": item}


@router.get("/aging/vendor-balances")
def vendor_balances(context=Depends(require_ap_read)) -> dict:
    vendor_balance_service.refresh_all(context.org_id)
    items = vendor_balance_service.list_balances(context.org_id)
    return {"request_id": context.request_id, "items": items}
