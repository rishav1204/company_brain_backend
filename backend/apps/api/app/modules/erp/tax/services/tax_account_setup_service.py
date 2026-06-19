from __future__ import annotations

from app.modules.erp.accounts_payable.engine.account_resolver import resolve_account_by_type
from app.modules.erp.coa.repositories.account_group_repository import account_group_repository
from app.modules.erp.coa.services.account_service import account_service

TAX_ACCOUNTS = (
    {"account_code": "2350", "account_name": "TDS Payable", "account_type": "tds_payable", "group_type": "liability", "nature": "credit"},
    {"account_code": "2351", "account_name": "TCS Payable", "account_type": "tcs_payable", "group_type": "liability", "nature": "credit"},
    {"account_code": "1350", "account_name": "TDS Receivable", "account_type": "tds_receivable", "group_type": "asset", "nature": "debit"},
    {"account_code": "1351", "account_name": "TCS Receivable", "account_type": "tcs_receivable", "group_type": "asset", "nature": "debit"},
)


class TaxAccountSetupService:
    def _find_group(self, org_id: str, *, group_type: str, company_id: str | None = None) -> str | None:
        for group in account_group_repository.list(org_id, company_id=company_id, limit=500):
            if str(group.get("group_type")) == group_type:
                return str(group["id"])
        return None

    def _ensure_group(
        self,
        org_id: str,
        *,
        group_code: str,
        group_name: str,
        group_type: str,
        nature: str,
        company_id: str | None = None,
        auto_create: bool,
    ) -> str | None:
        for group in account_group_repository.list(org_id, company_id=company_id, limit=500):
            if str(group.get("group_code")) == group_code:
                return str(group["id"])
        if not auto_create:
            return self._find_group(org_id, group_type=group_type, company_id=company_id)
        row = account_group_repository.create(
            org_id,
            group_name=group_name,
            group_code=group_code,
            group_type=group_type,
            nature=nature,
            company_id=company_id,
        )
        return str(row["id"])

    def ensure_tax_accounts(
        self,
        org_id: str,
        *,
        company_id: str | None = None,
        auto_create: bool = True,
    ) -> dict:
        created: list[dict] = []
        existing: list[dict] = []

        liability_group_id = self._ensure_group(
            org_id,
            group_code="TAX_LIABILITY",
            group_name="Tax Liabilities",
            group_type="liability",
            nature="credit",
            company_id=company_id,
            auto_create=auto_create,
        )
        asset_group_id = self._ensure_group(
            org_id,
            group_code="TAX_RECEIVABLE",
            group_name="Tax Receivables",
            group_type="asset",
            nature="debit",
            company_id=company_id,
            auto_create=auto_create,
        )

        for spec in TAX_ACCOUNTS:
            account_type = spec["account_type"]
            found_id = resolve_account_by_type(org_id, account_type)
            if found_id:
                existing.append({"account_type": account_type, "account_id": found_id})
                continue
            if not auto_create:
                continue
            group_id = liability_group_id if spec["group_type"] == "liability" else asset_group_id
            if not group_id:
                raise ValueError(f"Cannot create {account_type} account — COA group missing")
            row = account_service.create(
                org_id,
                account_code=spec["account_code"],
                account_name=spec["account_name"],
                account_type=account_type,
                group_id=group_id,
                parent_account_id=None,
                is_postable=True,
                company_id=company_id,
            )
            created.append({"account_type": account_type, "account_id": row.get("id"), "account_code": spec["account_code"]})

        return {"created": created, "existing": existing}

    def require_tds_payable(self, org_id: str, *, auto_create: bool = True) -> str:
        result = self.ensure_tax_accounts(org_id, auto_create=auto_create)
        account_id = resolve_account_by_type(org_id, "tds_payable")
        if not account_id:
            raise ValueError("TDS Payable account required — run POST /tds/setup/accounts or enable auto_create")
        return account_id

    def require_tcs_payable(self, org_id: str, *, auto_create: bool = True) -> str:
        result = self.ensure_tax_accounts(org_id, auto_create=auto_create)
        account_id = resolve_account_by_type(org_id, "tcs_payable")
        if not account_id:
            raise ValueError("TCS Payable account required — run POST /tds/setup/accounts or enable auto_create")
        return account_id


tax_account_setup_service = TaxAccountSetupService()
