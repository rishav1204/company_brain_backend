import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import auth_headers
from tests.integration_helpers import ORG_A, ORG_B, unique_key


client = TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("org_id", [ORG_A, ORG_B])
def test_graph_queries_are_org_scoped_contract(org_id: str, require_integration_infra) -> None:
    headers = auth_headers(org_id=org_id, user_id="u1", roles=["tenant_admin"])
    response = client.get("/api/v1/graph/queries/decision-impact", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["verification_status"] == "graph_decision_impact_query_completed"
    assert isinstance(body["rows"], list)


def test_sources_are_org_scoped_contract(require_integration_infra) -> None:
    headers_a = auth_headers(org_id=ORG_A, user_id="u1", roles=["tenant_admin"])
    headers_b = auth_headers(org_id=ORG_B, user_id="u2", roles=["tenant_admin"])
    config_ref = unique_key("cfg-iso")
    create = client.post(
        "/api/v1/sources",
        headers=headers_a,
        json={"source_type": "docs", "config_ref": config_ref},
    )
    assert create.status_code == 200
    source_id = create.json()["id"]

    list_a = client.get("/api/v1/sources", headers=headers_a)
    list_b = client.get("/api/v1/sources", headers=headers_b)
    assert list_a.status_code == 200
    assert list_b.status_code == 200
    ids_a = {item["id"] for item in list_a.json()["items"]}
    ids_b = {item["id"] for item in list_b.json()["items"]}
    assert source_id in ids_a
    assert source_id not in ids_b
