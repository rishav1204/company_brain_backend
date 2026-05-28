import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import observability_service as obs_module
from app.services import otel as otel_module
from tests.conftest import auth_headers


client = TestClient(app, raise_server_exceptions=False)


def test_observability_status_endpoint() -> None:
    response = client.get("/api/v1/observability/status", headers=auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["verification_status"] == "observability_stack_status"
    assert "otel_ready" in body["status"]
    assert "prod_requirements_met" in body["status"]


def test_metrics_include_observability_counters() -> None:
    response = client.get("/api/v1/metrics", headers=auth_headers())
    assert response.status_code == 200
    metrics = response.json()["metrics"]
    assert "log_sink_success_count" in metrics
    assert "trace_span_count" in metrics
    assert "prod_requirements_met" in metrics


def test_prometheus_export_includes_observability_gauges() -> None:
    response = client.get("/api/v1/metrics/prometheus", headers=auth_headers())
    assert response.status_code == 200
    text = response.text
    assert "app_log_sink_configured" in text
    assert "app_observability_prod_requirements_met" in text
    assert "app_trace_span_count" in text


def test_validate_prod_observability_requires_central_sink_in_prod(monkeypatch) -> None:
    monkeypatch.setattr(obs_module.settings, "app_env", "prod")
    monkeypatch.setattr(obs_module.settings, "observability_require_in_prod", True)
    monkeypatch.setattr(obs_module.settings, "otel_enabled", False)
    monkeypatch.setattr(obs_module.settings, "log_sink_url", "")
    monkeypatch.setattr(otel_module, "_otel_ready", False)
    valid, issues = obs_module.validate_prod_observability()
    assert valid is False
    assert "central_observability_missing" in issues


def test_validate_prod_observability_passes_with_log_sink(monkeypatch) -> None:
    monkeypatch.setattr(obs_module.settings, "app_env", "prod")
    monkeypatch.setattr(obs_module.settings, "observability_require_in_prod", True)
    monkeypatch.setattr(obs_module.settings, "otel_enabled", False)
    monkeypatch.setattr(obs_module.settings, "log_sink_url", "https://logs.example/ingest")
    monkeypatch.setattr(otel_module, "_otel_ready", False)
    valid, issues = obs_module.validate_prod_observability()
    assert valid is True
    assert issues == []


def test_log_event_records_sink_success(monkeypatch) -> None:
    from app.services.logger import log_event
    from app.services.metrics import metrics_store

    monkeypatch.setattr("app.services.logger.settings.log_sink_url", "https://logs.example/ingest")

    class _Resp:
        status_code = 202

    monkeypatch.setattr("app.services.logger.httpx.post", lambda *args, **kwargs: _Resp())
    before = metrics_store.snapshot().log_sink_success_count
    log_event("test.event", detail="ok")
    after = metrics_store.snapshot().log_sink_success_count
    assert after == before + 1


def test_trace_span_increments_counter() -> None:
    from app.services.metrics import metrics_store
    from app.services.trace import trace_span

    before = metrics_store.snapshot().trace_span_count
    with trace_span("test.span", component="unit"):
        pass
    after = metrics_store.snapshot().trace_span_count
    assert after == before + 1
