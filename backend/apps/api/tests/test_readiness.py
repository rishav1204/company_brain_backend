from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_ready_without_dependencies(monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "postgres_dsn", "")
    monkeypatch.setattr(settings, "redis_url", "")
    response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"]["postgres"] == "skipped"
    assert payload["checks"]["redis"] == "skipped"
    assert "observability" in payload["checks"]
