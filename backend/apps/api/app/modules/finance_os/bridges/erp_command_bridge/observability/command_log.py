"""Bridge observability — structured logs + optional OTEL span fields."""

from __future__ import annotations

from typing import Any


def log_command(
    event: str,
    *,
    command_id: str,
    command_type: str,
    org_id: str,
    actor_id: str,
    status: str | None = None,
    lifecycle: str | None = None,
    duration_ms: float | None = None,
    erp_module: str | None = None,
    erp_service: str | None = None,
    erp_fn: str | None = None,
    entity_id: str | None = None,
    correlation_id: str | None = None,
    attempt: int | None = None,
    company_id: str | None = None,
    approval_id: str | None = None,
    workflow_id: str | None = None,
    error_code: str | None = None,
    error_class: str | None = None,
    **extra: Any,
) -> None:
    payload = {
        "command_id": command_id,
        "command_type": command_type,
        "org_id": org_id,
        "actor_id": actor_id,
        "status": status,
        "lifecycle": lifecycle,
        "duration_ms": duration_ms,
        "erp_module": erp_module,
        "erp_service": erp_service,
        "erp_fn": erp_fn,
        "entity_id": entity_id,
        "correlation_id": correlation_id,
        "attempt": attempt,
        "company_id": company_id,
        "approval_id": approval_id,
        "workflow_id": workflow_id,
        "error_code": error_code,
        "error_class": error_class,
        **extra,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    try:
        from app.services.logger import log_event

        log_event(event, **payload)
    except Exception:
        pass
    try:
        from app.services.otel import trace_span

        with trace_span(event, **{k: str(v) for k, v in payload.items() if k != "event"}):
            pass
    except Exception:
        pass
