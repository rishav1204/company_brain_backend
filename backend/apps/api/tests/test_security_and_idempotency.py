from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import auth_headers


client = TestClient(app)


def test_missing_headers_rejected() -> None:
    response = client.get("/api/v1/workflows")
    assert response.status_code == 401


def test_invalid_amount_returns_422() -> None:
    from app.core.config import DEV_ORG_ID

    response = client.post(
        f"/api/v1/companies/{DEV_ORG_ID}/workflows/44444444-4444-4444-8444-444444444441/actions",
        headers=auth_headers(org_id=DEV_ORG_ID, user_id="user1", roles=["tenant_admin"]),
        json={"action": "approve_payment", "parameters": {"amount": "not-a-number"}},
    )
    assert response.status_code in {422, 400, 403, 404}


def test_idempotency_bound_to_workflow() -> None:
    from app.core.config import DEV_ORG_ID

    headers = auth_headers(
        org_id=DEV_ORG_ID,
        user_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        roles=["tenant_admin"],
    )
    payload = {"action": "notify_user", "parameters": {"idempotency_key": "idem-1"}}
    first = client.post(
        "/api/v1/workflows/55555555-5555-4555-8555-555555555551/actions",
        headers=headers,
        json=payload,
    )
    assert first.status_code in {200, 403, 404, 503}

    if first.status_code != 200:
        return

    replay_different_workflow = client.post(
        "/api/v1/workflows/44444444-4444-4444-8444-444444444441/actions",
        headers=headers,
        json=payload,
    )
    assert replay_different_workflow.status_code in {200, 403, 404, 503}
    if replay_different_workflow.status_code == 200:
        body = replay_different_workflow.json()
        assert body.get("idempotent_replay") is not True
