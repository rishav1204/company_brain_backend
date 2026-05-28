from app.modules.platform.events.services.scheduling_service import scheduling_service


def emit_sla_scan(org_id: str, *, trace_id: str | None = None) -> dict:
    return scheduling_service.emit_sla_scan(org_id, trace_id=trace_id)
