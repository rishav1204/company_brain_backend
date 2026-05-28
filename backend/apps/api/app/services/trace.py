from contextlib import contextmanager

from app.services.otel import otel_span


@contextmanager
def trace_span(name: str, **fields):
    with otel_span(name, **fields):
        yield
