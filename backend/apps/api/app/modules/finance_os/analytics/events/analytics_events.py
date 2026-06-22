from __future__ import annotations

from typing import Any

from app.modules.platform.events.services.event_service import platform_event_service


def emit_kpi_updated(org_id: str, *, count: int, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="kpi.updated",
        org_id=org_id,
        source="finance_os.analytics",
        payload={"count": count},
        trace_id=trace_id,
    )


def emit_insight_generated(org_id: str, *, count: int, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="insight.generated",
        org_id=org_id,
        source="finance_os.analytics",
        payload={"count": count},
        trace_id=trace_id,
    )


def emit_risk_detected(org_id: str, *, anomaly_type: str, severity: str, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="risk.detected",
        org_id=org_id,
        source="finance_os.analytics",
        payload={"anomaly_type": anomaly_type, "severity": severity},
        trace_id=trace_id,
    )


def emit_dashboard_refreshed(org_id: str, *, snapshot_date: str, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="dashboard.refreshed",
        org_id=org_id,
        source="finance_os.analytics",
        payload={"snapshot_date": snapshot_date},
        trace_id=trace_id,
    )


def emit_analytics_refresh_requested(org_id: str, *, reason: str, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="analytics.refresh.requested",
        org_id=org_id,
        source="finance_os.analytics",
        payload={"reason": reason},
        trace_id=trace_id,
    )
