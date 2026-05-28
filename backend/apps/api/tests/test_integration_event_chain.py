from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import auth_headers
from tests.integration_helpers import ORG_A, unique_key


client = TestClient(app, raise_server_exceptions=False)
headers = auth_headers(org_id=ORG_A, user_id="user1", roles=["tenant_admin"])


def test_event_chain_enqueue_worker_and_topology(require_integration_infra) -> None:
    topology = client.get("/api/v1/queue/topology", headers=headers)
    assert topology.status_code == 200
    assert "finance.action" in topology.json()["topics"]

    enqueue = client.post(
        "/api/v1/queue/enqueue",
        headers=headers,
        json={
            "idempotency_key": unique_key("integration-chain"),
            "payload": {"event_type": "source.sync.started", "source_id": "s1"},
        },
    )
    assert enqueue.status_code == 200
    assert enqueue.json()["accepted"] is True

    worker = client.post("/api/v1/ops/worker/run-batch?iterations=2", headers=headers)
    assert worker.status_code == 200
    assert worker.json()["batch_summary"]["iterations"] == 2
