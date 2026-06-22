from __future__ import annotations

import base64

from app.modules.erp.reporting.engine.export_engine import render_export
from app.modules.erp.reporting.events.report_events import emit_report_exported, emit_reports_generate_completed
from app.modules.erp.reporting.repositories.report_runs_repository import report_runs_repository
from app.modules.erp.reporting.services.report_engine import report_engine


class ExportService:
    _SYNC_ROW_THRESHOLD = 5000

    def enqueue(
        self,
        org_id: str,
        *,
        report_type: str,
        fmt: str,
        filters: dict | None = None,
        created_by: str | None = None,
    ) -> dict:
        run = report_runs_repository.create(
            org_id, report_type=report_type, filters={**(filters or {}), "format": fmt}, created_by=created_by
        )
        from app.modules.erp.reporting.events.report_events import emit_reports_generate_requested

        emit_reports_generate_requested(org_id, run_id=str(run["id"]), report_type=report_type, filters=filters or {})
        return run

    def process_run(self, org_id: str, *, run_id: str) -> dict:
        run = report_runs_repository.get(org_id, run_id=run_id)
        if not run:
            raise ValueError("Report run not found")
        report_type = str(run.get("report_type") or "")
        filters = run.get("filters") or {}
        fmt = str(filters.get("format") or "csv")
        try:
            payload = report_engine.fetch_payload(org_id, report_type=report_type, filters=filters)
            content, mime = render_export(report_type, payload, fmt=fmt)
            file_ref = f"data:{mime};base64,{base64.b64encode(content).decode('ascii')}"
            report_runs_repository.mark_completed(org_id, run_id=run_id, file_ref=file_ref)
            emit_report_exported(org_id, run_id=run_id, report_type=report_type)
            emit_reports_generate_completed(org_id, run_id=run_id, report_type=report_type)
            return {"run_id": run_id, "status": "completed", "file_ref": file_ref}
        except Exception as exc:
            report_runs_repository.mark_failed(org_id, run_id=run_id, error_message=str(exc))
            raise


export_service = ExportService()
