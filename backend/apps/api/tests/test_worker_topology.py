from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import auth_headers
from tests.integration_helpers import ORG_A, unique_key


client = TestClient(app, raise_server_exceptions=False)
headers = auth_headers(org_id=ORG_A, user_id="user1", roles=["tenant_admin"])


def test_queue_topology_endpoint_shape(require_integration_infra) -> None:
    response = client.get("/api/v1/queue/topology", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "queues" in body
    assert "topics" in body
    assert "ingestion.sync" in body["queues"]
    assert "finance.process" in body["topics"]
    assert body["dlq_suffix"] == ".dlq"


def test_worker_batch_endpoint_returns_summary(require_integration_infra) -> None:
    response = client.post("/api/v1/ops/worker/run-batch?iterations=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["verification_status"] == "worker_batch_invoked"
    summary = body["batch_summary"]
    assert summary["iterations"] == 2
    assert "lag_snapshot" in summary
    assert isinstance(summary["lag_snapshot"], dict)
