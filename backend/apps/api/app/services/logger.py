import json
import logging
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.services.metrics import metrics_store

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
_logger = logging.getLogger("company_brain_backend")


def log_event(event_type: str, **fields) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "service": settings.otel_service_name,
        **fields,
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
