from __future__ import annotations

from typing import Any

from app.modules.platform.events.services.event_service import platform_event_service


def emit_period_soft_locked(org_id: str, *, period_id: str, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="erp.period.soft_locked",
        org_id=org_id,
        source="erp.fiscal",
        entity_type="fiscal_period",
        entity_id=period_id,
        payload={"period_id": period_id},
        trace_id=trace_id,
    )


def emit_period_hard_locked(org_id: str, *, period_id: str, trace_id: str | None = None) -> dict[str, Any]:
    platform_event_service.publish(
        event_type="erp.fiscal_period.locked",
        org_id=org_id,
        source="erp.fiscal",
        entity_type="fiscal_period",
        entity_id=period_id,
        payload={"fiscal_period_id": period_id, "status": "hard_locked"},
        trace_id=trace_id,
    )
    return platform_event_service.publish(
        event_type="erp.period.hard_locked",
        org_id=org_id,
        source="erp.fiscal",
        entity_type="fiscal_period",
        entity_id=period_id,
        payload={"period_id": period_id},
        trace_id=trace_id,
    )


def emit_period_closed(org_id: str, *, period_id: str, trace_id: str | None = None) -> dict[str, Any]:
    platform_event_service.publish(
        event_type="erp.fiscal_period.closed",
        org_id=org_id,
        source="erp.fiscal",
        entity_type="fiscal_period",
        entity_id=period_id,
        payload={"fiscal_period_id": period_id, "status": "closed"},
        trace_id=trace_id,
    )
    return platform_event_service.publish(
        event_type="erp.period.closed",
        org_id=org_id,
        source="erp.fiscal",
        entity_type="fiscal_period",
        entity_id=period_id,
        payload={"period_id": period_id},
        trace_id=trace_id,
    )


def emit_period_reopened(org_id: str, *, period_id: str, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="erp.period.reopened",
        org_id=org_id,
        source="erp.fiscal",
        entity_type="fiscal_period",
        entity_id=period_id,
        payload={"period_id": period_id},
        trace_id=trace_id,
    )


def emit_period_opened(org_id: str, *, period_id: str, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="erp.period.opened",
        org_id=org_id,
        source="erp.fiscal",
        entity_type="fiscal_period",
        entity_id=period_id,
        payload={"period_id": period_id},
        trace_id=trace_id,
    )
