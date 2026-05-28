from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import auth_headers


client = TestClient(app)


def test_missing_headers_rejected() -> None:
    response = client.get("/api/v1/workflows")
    assert response.status_code == 401


def test_invalid_amount_returns_422() -> None:
    response = client.post(
        "/api/v1/companies/org-demo/workflows/wf-ap-1/actions",
        headers=auth_headers(org_id="org-demo", user_id="user1", roles=["tenant_admin"]),
        json={"action": "approve_payment", "parameters": {"amount": "not-a-number"}},
    )
    assert response.status_code == 422


def test_idempotency_bound_to_workflow() -> None:
    headers = auth_headers(org_id="org-demo", user_id="user1", roles=["tenant_admin"])
    payload = {"action": "notify_user", "parameters": {"idempotency_key": "idem-1"}}
    first = client.post("/api/v1/workflows/wf-close-1/actions", headers=headers, json=payload)
    assert first.status_code == 200

    replay_different_workflow = client.post("/api/v1/workflows/wf-ap-1/actions", headers=headers, json=payload)
    assert replay_different_workflow.status_code == 200
    body = replay_different_workflow.json()
    assert body.get("idempotent_replay") is not True
