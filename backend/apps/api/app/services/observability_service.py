from app.core.config import settings
from app.services.logger import log_event
from app.services.metrics import metrics_store
from app.services.otel import init_otel, is_otel_ready


def observability_config() -> dict:
    return {
        "app_env": settings.app_env,
        "otel_enabled": settings.otel_enabled,
        "otel_exporter_configured": bool(settings.otel_exporter_otlp_endpoint.strip()),
        "otel_ready": is_otel_ready(),
        "log_sink_configured": bool(settings.log_sink_url.strip()),
        "log_level": settings.log_level,
        "observability_require_in_prod": settings.observability_require_in_prod,
    }


def validate_prod_observability() -> tuple[bool, list[str]]:
    if settings.app_env.lower() != "prod" or not settings.observability_require_in_prod:
        return True, []
    issues: list[str] = []
    if settings.otel_enabled and not settings.otel_exporter_otlp_endpoint.strip():
        issues.append("otel_enabled_without_exporter")
    if not is_otel_ready() and not settings.log_sink_url.strip():
        issues.append("central_observability_missing")
    return len(issues) == 0, issues


def probe_log_sink() -> dict:
    if not settings.log_sink_url.strip():
        return {"status": "skipped", "detail": "log_sink_not_configured"}
    try:
        import httpx

        response = httpx.post(
            settings.log_sink_url,
            json={
                "event_type": "observability.probe",
                "source": settings.otel_service_name,
                "detail": "startup_or_health_probe",
            },
            timeout=2.0,
        )
        if response.status_code >= 400:
            metrics_store.incr_log_sink_failure()
            return {"status": "error", "detail": f"http_{response.status_code}"}
        metrics_store.incr_log_sink_success()
        return {"status": "ok"}
    except Exception as exc:
        metrics_store.incr_log_sink_failure()
        return {"status": "error", "detail": str(exc)}


def observability_status(probe_sink: bool = False) -> dict:
    config = observability_config()
    valid, issues = validate_prod_observability()
    snapshot = metrics_store.snapshot()
    queue_lags: dict[str, int] = {}
    try:
        from app.modules.platform.events.queues.queue_manager import queue_manager
        from app.services.event_topology import queue_groups

        for queue in queue_groups().values():
            queue_lags[queue] = queue_manager.lag(queue)
    except Exception:
        pass
    status = {
        **config,
        "prod_requirements_met": valid,
        "prod_requirement_issues": issues,
        "metrics": {
            "request_count": snapshot.request_count,
            "request_error_count": snapshot.request_error_count,
            "log_sink_success_count": snapshot.log_sink_success_count,
            "log_sink_failure_count": snapshot.log_sink_failure_count,
            "trace_span_count": snapshot.trace_span_count,
        },
        "queue_lags": queue_lags,
    }
    if probe_sink:
        status["log_sink_probe"] = probe_log_sink()
    return status


def startup_observability() -> dict:
    init_otel()
    report = observability_status(probe_sink=bool(settings.log_sink_url.strip()))
    valid, issues = validate_prod_observability()
    report["startup_valid"] = valid
    report["startup_issues"] = issues
    if not valid:
        log_event("observability.startup.invalid", issues=issues, **report)
    else:
        log_event("observability.startup.ok", **report)
    return report
