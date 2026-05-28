from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.erp.gl.security.gl_guard import require_finance_gl_admin
from app.modules.erp.gl.services.trial_balance_service import trial_balance_service

router = APIRouter()


@router.get("/trial-balance")
def generate_trial_balance(
    fiscal_period_id: str = Query(...),
    context=Depends(require_finance_gl_admin),
) -> dict:
    item = trial_balance_service.generate(context.org_id, fiscal_period_id=fiscal_period_id)
    try:
        from app.modules.platform.events.services.event_service import platform_event_service

        platform_event_service.publish(
            event_type="erp.trial_balance.generated",
            org_id=context.org_id,
            source="erp.gl",
            entity_type="fiscal_period",
            entity_id=fiscal_period_id,
            payload={"fiscal_period_id": fiscal_period_id, "balanced": item.get("balanced")},
        )
    except Exception:
        pass
    return {"request_id": context.request_id, "item": item}

