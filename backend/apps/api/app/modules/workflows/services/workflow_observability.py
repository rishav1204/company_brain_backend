from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from threading import Lock
from typing import Any, Iterator

from app.services.metrics import metrics_store

_approval_wait_ms: dict[str, list[int]] = defaultdict(list)
_bottleneck_lock = Lock()
_MAX_SAMPLES = 200


@contextmanager
def workflow_span(name: str, **attrs: Any) -> Iterator[None]:
    metrics_store.incr_trace_span()
    try:
        if __import__("app.core.config", fromlist=["settings"]).settings.otel_enabled:
            from opentelemetry import trace

            tracer = trace.get_tracer("workflow.engine")
            with tracer.start_as_current_span(name, attributes={k: str(v) for k, v in attrs.items()}):
                yield
        else:
            yield
    finally:
        pass


def record_transition() -> None:
    metrics_store.incr_workflow_transition()


def record_approval(decision: str) -> None:
    metrics_store.incr_workflow_approval(decision)


def record_sla_breach() -> None:
    metrics_store.incr_workflow_sla_breach()


def record_escalation() -> None:
    metrics_store.incr_workflow_escalation()


def record_retry() -> None:
    metrics_store.incr_workflow_retry()


def record_workflow_latency(org_id: str, instance_id: str, duration_ms: int) -> None:
    metrics_store.record_workflow_latency(duration_ms)
    try:
        from app.modules.workflows.repositories.latency_repository import latency_repo

        latency_repo.record_sample(
            org_id=org_id,
            metric_type="workflow_completion",
            duration_ms=duration_ms,
            workflow_instance_id=instance_id,
        )
    except Exception:
        pass


def record_approval_wait(org_id: str, approval_id: str, duration_ms: int) -> None:
    metrics_store.record_approval_wait(duration_ms)
    key = f"{org_id}:{approval_id}"
    with _bottleneck_lock:
        bucket = _approval_wait_ms[key]
        bucket.append(duration_ms)
        if len(bucket) > _MAX_SAMPLES:
            del bucket[0 : len(bucket) - _MAX_SAMPLES]
    try:
        from app.modules.workflows.repositories.latency_repository import latency_repo

        latency_repo.record_sample(
            org_id=org_id,
            metric_type="approval_wait",
            duration_ms=duration_ms,
        )
    except Exception:
        pass


def approval_bottleneck_summary(org_id: str) -> dict[str, Any]:
    with _bottleneck_lock:
        waits = [v for k, vals in _approval_wait_ms.items() if k.startswith(f"{org_id}:") for v in vals]
    if not waits:
        return {"org_id": org_id, "sample_count": 0, "avg_wait_ms": 0, "p95_wait_ms": 0}
    waits_sorted = sorted(waits)
    p95_idx = min(len(waits_sorted) - 1, int(len(waits_sorted) * 0.95))
    return {
        "org_id": org_id,
        "sample_count": len(waits_sorted),
        "avg_wait_ms": int(sum(waits_sorted) / len(waits_sorted)),
        "p95_wait_ms": waits_sorted[p95_idx],
    }
