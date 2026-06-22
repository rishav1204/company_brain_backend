from __future__ import annotations

from typing import Any

from app.modules.platform.events.services.event_service import platform_event_service


def emit_report_generated(org_id: str, *, report_type: str, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="report.generated",
        org_id=org_id,
        source="erp.reporting",
        payload={"report_type": report_type},
        trace_id=trace_id,
    )


def emit_report_exported(org_id: str, *, run_id: str, report_type: str, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="report.exported",
        org_id=org_id,
        source="erp.reporting",
        entity_type="report_run",
        entity_id=run_id,
        payload={"report_type": report_type, "run_id": run_id},
        trace_id=trace_id,
    )


def emit_report_snapshot_created(
    org_id: str, *, snapshot_id: str, report_type: str, period_key: str, trace_id: str | None = None
) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="report.snapshot.created",
        org_id=org_id,
        source="erp.reporting",
        entity_type="report_snapshot",
        entity_id=snapshot_id,
        payload={"report_type": report_type, "period_key": period_key},
        trace_id=trace_id,
    )


def emit_reports_generate_requested(
    org_id: str, *, run_id: str, report_type: str, filters: dict, trace_id: str | None = None
) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="reports.generate.requested",
        org_id=org_id,
        source="erp.reporting",
        entity_type="report_run",
        entity_id=run_id,
        payload={"run_id": run_id, "report_type": report_type, "filters": filters},
        trace_id=trace_id,
    )


def emit_reports_generate_completed(
    org_id: str, *, run_id: str, report_type: str, trace_id: str | None = None
) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="reports.generate.completed",
        org_id=org_id,
        source="erp.reporting",
        entity_type="report_run",
        entity_id=run_id,
        payload={"run_id": run_id, "report_type": report_type},
        trace_id=trace_id,
    )


def emit_reports_refresh_requested(org_id: str, *, reason: str, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="reports.refresh.requested",
        org_id=org_id,
        source="erp.reporting",
        payload={"reason": reason},
        trace_id=trace_id,
    )
