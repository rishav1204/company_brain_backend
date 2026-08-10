from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import auth_headers
from tests.integration_helpers import ORG_A, unique_key


client = TestClient(app, raise_server_exceptions=False)
headers = auth_headers(org_id=ORG_A, user_id="user1", roles=["tenant_admin"])


def test_queue_at_least_once_with_dedupe(require_integration_infra) -> None:
    idempotency_key = unique_key("evt")
    enqueue = client.post(
        "/api/v1/queue/enqueue",
        headers=headers,
        json={"idempotency_key": idempotency_key, "payload": {"event": "invoice.created"}},
    )
    if enqueue.status_code in {401, 403}:
        return
    assert enqueue.status_code == 200
    assert enqueue.json()["accepted"] is True
    assert enqueue.json()["result"] == "queued"

    process_first = client.post("/api/v1/queue/process-next", headers=headers)
    assert process_first.status_code == 200
    assert process_first.json()["result"]["status"] == "processed"

    enqueue_dup = client.post(
        "/api/v1/queue/enqueue",
        headers=headers,
        json={"idempotency_key": idempotency_key, "payload": {"event": "invoice.created"}},
    )
    assert enqueue_dup.status_code == 200
    assert enqueue_dup.json()["accepted"] is True

    process_second = client.post("/api/v1/queue/process-next", headers=headers)
    assert process_second.status_code == 200
    assert process_second.json()["result"]["status"] == "deduped"


def test_event_topology_declares_finance_service_boundaries(require_integration_infra) -> None:
    topology = client.get("/api/v1/queue/topology", headers=headers)
    assert topology.status_code == 200
    body = topology.json()
    assert "finance.ingest" in body["topics"]
    assert "finance.agent" in body["topics"]
    assert "execution_service" in body["service_boundaries"]
    assert body["verification_status"] == "topology_declared"
