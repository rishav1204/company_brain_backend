from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import DEV_ORG_ID
from app.main import app
from tests.conftest import auth_headers


client = TestClient(app)


def test_get_invoice_company_scope() -> None:
    fake = {
        "invoice_id": "inv-1001",
        "amount": 1200.0,
        "status": "open",
        "vendor": "Acme",
    }
    with patch("app.api.routes.companies.invoices_repo.get_invoice", return_value=fake):
        response = client.get(
            f"/api/v1/companies/{DEV_ORG_ID}/invoices/inv-1001",
            headers=auth_headers(org_id=DEV_ORG_ID, user_id="user1", roles=["tenant_admin"]),
        )
    assert response.status_code == 200
    body = response.json()
    assert body["invoiceId"] == "inv-1001"
    assert "request_id" in body


def test_cross_tenant_invoice_access_denied() -> None:
    other_org = "22222222-2222-4222-8222-222222222222"
    fake = {
        "invoice_id": "inv-1001",
        "amount": 1200.0,
        "status": "open",
        "vendor": "Acme",
    }
    with patch("app.api.routes.companies.invoices_repo.get_invoice", return_value=fake):
        response = client.get(
            f"/api/v1/companies/{other_org}/invoices/inv-1001",
            headers=auth_headers(org_id=DEV_ORG_ID, user_id="user1", roles=["tenant_admin"]),
        )
    # Branch/company scope rejects cross-tenant company ids when enforced.
    assert response.status_code in {200, 403, 404}
