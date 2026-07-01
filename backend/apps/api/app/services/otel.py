from contextlib import contextmanager
from time import perf_counter

from app.core.config import settings
from app.services.logger import log_event
from app.services.metrics import metrics_store

_otel_ready = False


def init_otel() -> bool:
    global _otel_ready
    if _otel_ready:
        return True
    if not settings.otel_enabled or not settings.otel_exporter_otlp_endpoint.strip():
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.propagate import set_global_textmap
        from opentelemetry.propagators.composite import CompositePropagator
        from opentelemetry.propagators.textmap import DefaultGetter, DefaultSetter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

        set_global_textmap(CompositePropagator([TraceContextTextMapPropagator()]))
        resource = Resource.create({"service.name": settings.otel_service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint.strip())
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _otel_ready = True
        log_event("otel.init.ok", endpoint=settings.otel_exporter_otlp_endpoint.strip())
        return True
    except Exception as exc:
        log_event("otel.init.failed", detail=str(exc))
        return False


def is_otel_ready() -> bool:
    return _otel_ready


def inject_trace_headers(carrier: dict) -> None:
    if not _otel_ready:
        return
    from opentelemetry.propagate import inject

    inject(carrier)


def extract_trace_context(carrier: dict) -> None:
    if not _otel_ready:
        return
    from opentelemetry.propagate import extract

    extract(carrier)


@contextmanager
def otel_span(name: str, **fields):
    metrics_store.incr_trace_span()
    if not _otel_ready:
        start = perf_counter()
        try:
            yield
        finally:
            duration_ms = (perf_counter() - start) * 1000
            log_event("trace.span", span=name, duration_ms=round(duration_ms, 2), **fields)
        return

    from opentelemetry import trace

    tracer = trace.get_tracer(settings.otel_service_name)
    with tracer.start_as_current_span(name) as span:
        for key, value in fields.items():
            span.set_attribute(str(key), str(value))
        ctx = trace.get_current_span().get_span_context()
        if ctx.trace_id:
            fields.setdefault("trace_id", format(ctx.trace_id, "032x"))
        if ctx.span_id:
            fields.setdefault("span_id", format(ctx.span_id, "016x"))
        yield
