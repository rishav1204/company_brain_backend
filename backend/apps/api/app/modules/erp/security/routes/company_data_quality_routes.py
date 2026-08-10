from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import build_request_context
from app.modules.core.iam.middleware.permission_guard import require_permission
from app.modules.erp.security.company_resolution_service import company_resolution_service

router = APIRouter(prefix="/erp/admin/company-data-quality", tags=["erp-admin"])


class RemediateFlagRequest(BaseModel):
    correct_company_id: str
    idempotency_key: str | None = None


@router.get("")
def list_flags(context=Depends(require_permission("org.admin"))) -> dict:
    flags = company_resolution_service.list_data_quality_flags(context.org_id)
    return {
        "request_id": context.request_id,
        "count": len(flags),
        "unresolved": company_resolution_service.flag_count(context.org_id),
        "items": flags,
    }


@router.post("/{flag_id}/remediate")
def remediate_flag(
    flag_id: str,
    request: RemediateFlagRequest,
    context=Depends(require_permission("org.admin")),
) -> dict:
    try:
        result = company_resolution_service.remediate_flag(
            context.org_id,
            flag_id=flag_id,
            correct_company_id=request.correct_company_id,
            remediated_by=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": result}


@router.post("/auto-remediate")
def auto_remediate(context=Depends(require_permission("org.admin"))) -> dict:
    result = company_resolution_service.bulk_auto_remediate(
        context.org_id,
        remediated_by=context.user_id,
    )
    return {"request_id": context.request_id, **result}


@router.post("/run-remediation")
def run_remediation(context=Depends(require_permission("org.admin"))) -> dict:
    from app.modules.erp.security.services.company_remediation_service import company_remediation_service

    py_result = company_remediation_service.run_python_pass(remediated_by=context.user_id)
    summary = company_remediation_service.summary()
    return {"request_id": context.request_id, "python_pass": py_result, "summary": summary}
