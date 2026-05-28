from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import auth_headers


client = TestClient(app)
headers = auth_headers(org_id="org-demo", user_id="user1", roles=["tenant_admin"])


def test_ingestion_start_and_complete() -> None:
    source = client.post("/api/v1/sources", headers=headers, json={"source_type": "erp", "config_ref": "cfg-1"})
    assert source.status_code == 200
    source_id = source.json()["id"]

    started = client.post(
        "/api/v1/ingestion/runs/start",
        headers=headers,
        json={"source_id": source_id, "trigger_mode": "polling"},
    )
    assert started.status_code == 200
    run_id = started.json()["run_id"]

    completed = client.post(
        "/api/v1/ingestion/runs/complete",
        headers=headers,
        json={"run_id": run_id, "success": True},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"


def test_queue_retry_and_dlq() -> None:
    enqueue = client.post(
        "/api/v1/queue/enqueue",
        headers=headers,
        json={"idempotency_key": "q-1", "payload": {"force_fail": True}},
    )
    assert enqueue.status_code == 200
    for _ in range(3):
        process = client.post("/api/v1/queue/process-next", headers=headers)
        assert process.status_code == 200
    terminal = process.json()["result"]["status"]
    assert terminal in {"retry", "dlq", "processed"}
