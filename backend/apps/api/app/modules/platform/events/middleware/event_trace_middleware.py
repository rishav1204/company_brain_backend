from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from app.services.metrics import metrics_store


@contextmanager
def trace_event_processing(event_type: str, queue: str) -> Iterator[None]:
    metrics_store.incr_trace_span()
    try:
        if __import__("app.core.config", fromlist=["settings"]).settings.otel_enabled:
            from opentelemetry import trace

            tracer = trace.get_tracer("platform.events")
            with tracer.start_as_current_span(
                "event.process",
                attributes={"event_type": event_type, "queue": queue},
            ):
                yield
        else:
            yield
    finally:
        pass
