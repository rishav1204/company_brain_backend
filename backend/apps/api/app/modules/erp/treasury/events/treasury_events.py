from __future__ import annotations

from typing import Any

from app.modules.platform.events.services.event_service import platform_event_service


def emit_cash_position_updated(org_id: str, *, position: dict, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="cash.position.updated",
        org_id=org_id,
        source="erp.treasury",
        entity_type="cash_position",
        entity_id=org_id,
        payload={"position": position},
        trace_id=trace_id,
    )


def emit_liquidity_alert_created(org_id: str, *, alert_id: str, alert_type: str, severity: str, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="liquidity_alert.created",
        org_id=org_id,
        source="erp.treasury",
        entity_type="liquidity_alert",
        entity_id=alert_id,
        payload={"alert_id": alert_id, "alert_type": alert_type, "severity": severity},
        trace_id=trace_id,
    )


def emit_cash_forecast_updated(org_id: str, *, horizon_days: int, forecast_cash_balance: float, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="cash.forecast.updated",
        org_id=org_id,
        source="erp.treasury",
        entity_type="cash_forecast",
        entity_id=org_id,
        payload={"horizon_days": horizon_days, "forecast_cash_balance": forecast_cash_balance},
        trace_id=trace_id,
    )


def emit_treasury_risk_detected(org_id: str, *, risk_type: str, severity: str, message: str, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="treasury.risk.detected",
        org_id=org_id,
        source="erp.treasury",
        entity_type="treasury_risk",
        entity_id=org_id,
        payload={"risk_type": risk_type, "severity": severity, "message": message},
        trace_id=trace_id,
    )


def emit_reconciliation_completed(
    org_id: str,
    *,
    reconciliation_id: str,
    bank_transaction_id: str,
    ledger_entry_id: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    from app.modules.erp.reconciliation.events.reconciliation_events import emit_reconciliation_completed as _emit

    return _emit(
        org_id,
        reconciliation_id=reconciliation_id,
        bank_transaction_id=bank_transaction_id,
        ledger_entry_id=ledger_entry_id,
        trace_id=trace_id,
    )
