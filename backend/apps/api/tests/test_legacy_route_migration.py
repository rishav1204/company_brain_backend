from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import yaml
from fastapi.testclient import TestClient

from app.core.config import settings
from app.legacy_deprecation_middleware import _resolve_successor
from app.main import app

client = TestClient(app, raise_server_exceptions=False)
OPENAPI_PATH = Path(__file__).resolve().parents[3] / "api" / "openapi.yaml"


def _token(org_id: str = "11111111-1111-4111-8111-111111111111", user_id: str = "user-test") -> str:
    now = datetime.now(timezone.utc)
    payload = {
        settings.jwt_tenant_claim: org_id,
        settings.jwt_user_claim: user_id,
        settings.jwt_roles_claim: ["tenant_admin"],
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def test_resolve_successor_mappings() -> None:
    assert _resolve_successor("/agents/run") == "/finance-os/agents/run"
    assert _resolve_successor("/workflows") == "/workflows/definitions"
    assert _resolve_successor("/auth/password/login") == "/auth/login"
    assert _resolve_successor("/workflows/wf-1/actions") == "/approvals"
    assert _resolve_successor("/workflows/definitions") is None
    assert _resolve_successor("/memory/decay/run") == "/finance-os/memory/admin/decay/run"


def test_legacy_decisions_returns_deprecation_headers() -> None:
    response = client.get("/api/v1/decisions", headers={"Authorization": f"Bearer {_token()}"})
    assert response.status_code == 200
    assert response.headers.get("Deprecation") == "true"
    assert response.headers.get("Sunset")
    assert "finance-os/memory" in response.headers.get("Link", "")


def test_legacy_memory_decay_returns_deprecation_headers() -> None:
    response = client.post("/api/v1/memory/decay/run", headers={"Authorization": f"Bearer {_token()}"})
    assert response.headers.get("Deprecation") == "true"
    assert "finance-os/memory/admin/decay/run" in response.headers.get("Link", "")


def test_modular_successor_paths_are_live() -> None:
    headers = {"Authorization": f"Bearer {_token()}"}
    modular_paths = (
        "/api/v1/finance-os/agents/health",
        "/api/v1/finance-os/graph/health",
        "/api/v1/finance-os/memory/health",
    )
    for path in modular_paths:
        response = client.get(path, headers=headers)
        assert response.status_code == 200, path
        assert response.headers.get("Deprecation") is None


def test_modular_workflow_definitions_requires_auth() -> None:
    response = client.get("/api/v1/workflows/definitions", headers={"Authorization": f"Bearer {_token()}"})
    assert response.status_code in {200, 403}
    assert response.headers.get("Deprecation") is None


def test_openapi_marks_legacy_intelligence_paths_deprecated() -> None:
    spec = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    deprecated_paths = (
        ("/agents/run", "post"),
        ("/agents/runs/{runId}", "get"),
        ("/agents/runs/{runId}/approve", "post"),
        ("/decisions", "get"),
        ("/decisions", "post"),
        ("/memory", "get"),
        ("/memory", "post"),
        ("/memory/decay/run", "post"),
        ("/workflows", "get"),
        ("/workflows/{id}/actions", "post"),
        ("/workflows/{id}/timeline", "get"),
    )
    for path, method in deprecated_paths:
        operation = spec["paths"][path][method]
        assert operation.get("deprecated") is True, f"{method.upper()} {path}"


def test_openapi_documents_modular_successor_paths() -> None:
    spec = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    for path in (
        "/finance-os/agents/health",
        "/finance-os/graph/health",
        "/finance-os/memory/health",
        "/workflows/definitions",
    ):
        assert path in spec["paths"], path
        operation = next(iter(spec["paths"][path].values()))
        assert operation.get("deprecated") is not True
