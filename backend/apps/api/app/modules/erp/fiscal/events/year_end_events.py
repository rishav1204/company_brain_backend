from __future__ import annotations

from typing import Any

from app.modules.platform.events.services.event_service import platform_event_service


def emit_fiscal_year_closed(org_id: str, *, fiscal_year_id: str, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="erp.fiscal_year.closed",
        org_id=org_id,
        source="erp.fiscal",
        entity_type="fiscal_year",
        entity_id=fiscal_year_id,
        payload={"fiscal_year_id": fiscal_year_id},
        trace_id=trace_id,
    )


def emit_year_end_completed(org_id: str, *, run_id: str, fiscal_year_id: str, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="erp.year_end.completed",
        org_id=org_id,
        source="erp.fiscal",
        entity_type="year_end_run",
        entity_id=run_id,
        payload={"run_id": run_id, "fiscal_year_id": fiscal_year_id},
        trace_id=trace_id,
    )
