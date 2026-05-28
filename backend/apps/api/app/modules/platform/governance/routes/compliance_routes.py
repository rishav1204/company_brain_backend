from fastapi import APIRouter, Depends, Query

from app.modules.platform.governance.api.deps import require_auditor_read, require_governance_write
from app.modules.platform.governance.services.compliance_service import compliance_service

router = APIRouter(tags=["governance-compliance"])


@router.get("/compliance/events")
def list_compliance_events(
    context=Depends(require_auditor_read),
    compliance_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    items = compliance_service.list_events(
        context.org_id, compliance_type=compliance_type, status=status, limit=limit
    )
    return {"request_id": context.request_id, "items": items}


@router.post("/compliance/gst/filed")
def record_gst_filed(
    context=Depends(require_governance_write),
    return_id: str = Query(...),
    period: str = Query(...),
    status: str = Query(default="filed"),
) -> dict:
    row = compliance_service.track_gst_filing(
        context.org_id, return_id=return_id, period=period, status=status
    )
    return {"request_id": context.request_id, "event": row}


@router.post("/compliance/gst/itc-mismatch")
def record_gst_itc_mismatch(
    context=Depends(require_governance_write),
    return_id: str = Query(...),
    delta_amount: float = Query(...),
) -> dict:
    row = compliance_service.track_gst_itc_mismatch(
        context.org_id, return_id=return_id, delta_amount=delta_amount
    )
    return {"request_id": context.request_id, "event": row}


@router.post("/compliance/gst/delayed-filing")
def record_gst_delayed(
    context=Depends(require_governance_write),
    return_id: str = Query(...),
    days_late: int = Query(...),
) -> dict:
    row = compliance_service.track_gst_delayed_filing(
        context.org_id, return_id=return_id, days_late=days_late
    )
    return {"request_id": context.request_id, "event": row}


@router.post("/compliance/tds/{tds_type}")
def record_tds(
    tds_type: str,
    context=Depends(require_governance_write),
    entity_id: str = Query(...),
    status: str = Query(default="completed"),
) -> dict:
    row = compliance_service.track_tds(
        context.org_id,
        compliance_type=tds_type,
        entity_id=entity_id,
        status=status,
        details={"recorded_by": context.user_id},
    )
    return {"request_id": context.request_id, "event": row}
