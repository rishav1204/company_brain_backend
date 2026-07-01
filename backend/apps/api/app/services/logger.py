import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.services.metrics import metrics_store

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
_logger = logging.getLogger("company_brain_backend")

_log_context: ContextVar[dict] = ContextVar("log_context", default={})


def bind_log_context(**fields) -> None:
    current = dict(_log_context.get())
    current.update({k: v for k, v in fields.items() if v is not None})
    _log_context.set(current)


def log_event(event_type: str, **fields) -> None:
    merged = {**_log_context.get(), **fields}
    if _otel_trace_fields():
        merged.update(_otel_trace_fields())
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "service": settings.otel_service_name,
        **merged,
    }
    serialized = json.dumps(payload, ensure_ascii=True)
    _logger.info(serialized)
    if not settings.log_sink_url.strip():
        return
    try:
        response = httpx.post(settings.log_sink_url.strip(), json=payload, timeout=2.0)
        if response.status_code >= 400:
            metrics_store.incr_log_sink_failure()
            return
        metrics_store.incr_log_sink_success()
    except Exception:
        metrics_store.incr_log_sink_failure()


def _otel_trace_fields() -> dict:
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if not ctx or not ctx.trace_id:
            return {}
        return {
            "trace_id": format(ctx.trace_id, "032x"),
            "span_id": format(ctx.span_id, "016x"),
        }
    except Exception:
        return {}
