from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import build_request_context
from app.modules.erp.reporting.schemas.reporting_schema import ExportRequest, ExportRunResponse, ExportStatusResponse
from app.modules.erp.reporting.security.reporting_guard import require_reporting_export, require_reporting_read
from app.modules.erp.reporting.services.export_service import export_service
from app.modules.erp.reporting.repositories.report_runs_repository import report_runs_repository
from app.services.repositories import audit_repo

router = APIRouter(tags=["erp-reports-export"])


@router.post("/export", response_model=ExportRunResponse)
def create_export(body: ExportRequest, context=Depends(build_request_context)) -> ExportRunResponse:
    require_reporting_export(context.user)
    run = export_service.enqueue(
        context.org_id,
        report_type=body.report_type,
        fmt=body.format,
        filters=body.filters,
        created_by=context.user_id,
    )
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="report.exported",
        object_ref=f"erp:report:{body.report_type}:{run.get('id')}",
    )
    return ExportRunResponse(run_id=str(run["id"]), status=str(run.get("status") or "queued"), report_type=body.report_type)


@router.get("/export/{run_id}", response_model=ExportStatusResponse)
def export_status(run_id: str, context=Depends(build_request_context)) -> ExportStatusResponse:
    require_reporting_read(context.user)
    run = report_runs_repository.get(context.org_id, run_id=run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Export run not found")
    if run.get("file_ref"):
        audit_repo.create_log(
            org_id=context.org_id,
            actor_type="user",
            actor_id=context.user_id,
            event_type="report.downloaded",
            object_ref=f"erp:report:export:{run_id}",
        )
    return ExportStatusResponse(
        run_id=run_id,
        status=str(run.get("status") or ""),
        report_type=str(run.get("report_type") or ""),
        file_ref=run.get("file_ref"),
        error_message=run.get("error_message"),
    )
