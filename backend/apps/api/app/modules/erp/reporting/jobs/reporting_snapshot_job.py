from __future__ import annotations

from app.modules.erp.reporting.events.report_events import emit_report_snapshot_created
from app.modules.erp.reporting.repositories.schema_repository import reporting_schema_repository
from app.modules.erp.reporting.repositories.snapshots_repository import snapshots_repository
from app.modules.erp.reporting.services.report_engine import report_engine


def freeze_period_snapshot(
    org_id: str,
    *,
    report_type: str,
    period_key: str,
    filters: dict,
    created_by: str | None = None,
) -> dict:
    if not reporting_schema_repository.schema_ready():
        return {"status": "skipped", "reason": "schema_not_ready"}
    payload = report_engine.fetch_payload(org_id, report_type=report_type, filters={**filters, **{"period_key": period_key}})
    row = snapshots_repository.create(
        org_id,
        report_type=report_type,
        period_key=period_key,
        payload=payload,
        created_by=created_by,
    )
    emit_report_snapshot_created(
        org_id,
        snapshot_id=str(row.get("id")),
        report_type=report_type,
        period_key=period_key,
    )
    return row
