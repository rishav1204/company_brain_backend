from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import auth_headers


client = TestClient(app)
headers = auth_headers(org_id="org-demo", user_id="user1", roles=["tenant_admin"])


def test_retrieval_eval_endpoint() -> None:
    response = client.post(
        "/api/v1/retrieval/eval",
        headers=headers,
        json={"query": "approval policy", "relevant_markers": ["approval", "policy"], "top_k": 5},
    )
    assert response.status_code == 200
