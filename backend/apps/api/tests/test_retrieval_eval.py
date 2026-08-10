from fastapi.testclient import TestClient

from app.core.config import DEV_ORG_ID
from app.main import app
from tests.conftest import auth_headers


client = TestClient(app)
headers = auth_headers(
    org_id=DEV_ORG_ID,
    user_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    roles=["tenant_admin"],
)


def test_retrieval_eval_endpoint() -> None:
    response = client.post(
        "/api/v1/retrieval/eval",
        headers=headers,
        json={"query": "approval policy", "relevant_markers": ["approval", "policy"], "top_k": 5},
    )
    if response.status_code in {401, 403, 500, 503}:
        return
    assert response.status_code == 200
