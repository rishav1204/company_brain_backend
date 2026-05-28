from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import auth_headers
from tests.integration_helpers import ORG_A, unique_key


client = TestClient(app, raise_server_exceptions=False)
headers = auth_headers(org_id=ORG_A, user_id="user1", roles=["tenant_admin"])


def test_identity_resolution_persists_profile(require_integration_infra) -> None:
    response = client.post(
        "/api/v1/identity/resolve",
        headers=headers,
        json={
            "aliases": ["Vendor A", "vendor_a", "VENDOR A"],
            "canonical_type": "vendor",
            "source": "erp",
            "source_key": "name",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["resolved"]["canonical_type"] == "vendor"
    assert body["resolved"]["canonical_key"] == "vendor_a"
    assert body["profile"]["id"]
    assert body["verification_status"] == "identity_resolution_v2"


def test_embedding_worker_endpoint_contract(require_integration_infra) -> None:
    source = client.post(
        "/api/v1/sources",
        headers=headers,
        json={"source_type": "docs", "config_ref": unique_key("cfg-docs")},
    )
    assert source.status_code == 200
    source_id = source.json()["id"]
    response = client.post(
        "/api/v1/ingestion/workers/embeddings/ingest",
        headers=headers,
        json={
            "source_id": source_id,
            "title": "AP delay postmortem",
            "content": "Urgent payment hold due to vendor mismatch and blocked approval chain.",
            "doc_type": "postmortem",
        },
    )
    # Without OpenAI key in CI, endpoint must fail closed with 503 rather than silently succeed.
    assert response.status_code in {200, 503}
    if response.status_code == 503:
        assert "Embedding worker unavailable" in response.json()["detail"]
    else:
        result = response.json()["embedding_result"]
        assert result["status"] == "completed"
        assert result["chunks_written"] >= 1
