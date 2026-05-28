from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.platform.governance.api.deps import require_auditor_read, require_governance_write
from app.modules.platform.governance.repositories.violation_repository import violation_repository
from app.modules.platform.governance.services.governance_service import GovernanceViolation, governance_service
from app.modules.platform.governance.services.risk_service import risk_service

router = APIRouter(tags=["governance"])


@router.get("/governance/violations")
def list_violations(context=Depends(require_auditor_read), limit: int = Query(default=50, le=200)) -> dict:
    items = violation_repository.list_open(context.org_id, limit=limit)
    return {"request_id": context.request_id, "items": items}


@router.post("/governance/violations/{violation_id}/resolve")
def resolve_violation(violation_id: str, context=Depends(require_governance_write)) -> dict:
    row = violation_repository.resolve(context.org_id, violation_id, resolved_by=context.user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Violation not found")
    return {"request_id": context.request_id, "violation": row}


@router.post("/governance/evaluate")
def evaluate_action(
    context=Depends(require_governance_write),
    action: str = Query(...),
    created_by: str | None = Query(default=None),
) -> dict:
    try:
        result = governance_service.evaluate_action(
            context.org_id,
            action=action,
            attrs=context.attrs or {},
            roles=context.roles,
            created_by=created_by,
            actor_user_id=context.user_id,
            request_id=context.request_id,
            trace_id=getattr(context, "trace_id", context.request_id),
        )
        return {"request_id": context.request_id, **result}
    except GovernanceViolation as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/governance/risk/payment")
def assess_payment_risk(
    context=Depends(require_governance_write),
    payment_id: str = Query(...),
    amount: float = Query(...),
) -> dict:
    return risk_service.assess_payment_risk(
        context.org_id,
        payment_id=payment_id,
        amount=amount,
        attrs={"roles": context.roles, **(context.attrs or {})},
    )
