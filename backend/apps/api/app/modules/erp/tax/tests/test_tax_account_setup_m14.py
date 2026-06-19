from app.modules.erp.tax.services.tax_account_setup_service import TAX_ACCOUNTS, TaxAccountSetupService


def test_tax_accounts_spec_complete() -> None:
    types = {a["account_type"] for a in TAX_ACCOUNTS}
    assert "tds_payable" in types
    assert "tcs_payable" in types
    assert "tds_receivable" in types
    assert "tcs_receivable" in types


def test_tax_account_setup_service_has_ensure() -> None:
    svc = TaxAccountSetupService()
    assert hasattr(svc, "ensure_tax_accounts")
    assert hasattr(svc, "require_tds_payable")
