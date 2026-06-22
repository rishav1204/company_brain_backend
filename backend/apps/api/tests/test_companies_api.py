from fastapi.testclient import TestClient

from app.core.config import DEV_ORG_ID
from app.main import app
from tests.conftest import auth_headers


client = TestClient(app)


def test_get_invoice_company_scope() -> None:
    response = client.get(
        f"/api/v1/companies/{DEV_ORG_ID}/invoices/inv-1001",
        headers=auth_headers(org_id=DEV_ORG_ID, user_id="user1", roles=["tenant_admin"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["invoiceId"] == "inv-1001"
    assert "request_id" in body


def test_cross_tenant_invoice_access_denied() -> None:
    response = client.get(
        "/api/v1/companies/org-other/invoices/inv-1001",
        headers=auth_headers(org_id="org-demo", user_id="user1", roles=["tenant_admin"]),
    )
    assert response.status_code == 403
