from __future__ import annotations

from app.modules.erp.coa.repositories.account_group_repository import account_group_repository
from app.modules.erp.coa.repositories.account_repository import account_repository
from app.modules.erp.coa.repositories.coa_version_repository import coa_version_repository
from app.modules.erp.coa.repositories.mapping_repository import mapping_repository


class CoaVersionService:
    def snapshot_current(
        self,
        org_id: str,
        *,
        fiscal_year: str,
        version_label: str = "default",
        effective_from: str,
        effective_to: str | None = None,
        company_id: str | None = None,
    ) -> dict:
        snapshot = {
            "accounts": account_repository.list(org_id, company_id=company_id, limit=5000),
            "groups": account_group_repository.list(org_id, company_id=company_id, limit=2000),
            "gst_mappings": mapping_repository.list_gst_mappings(org_id, company_id=company_id),
            "financial_mappings": mapping_repository.list_financial_mappings(org_id, company_id=company_id),
        }
        return coa_version_repository.create(
            org_id,
            fiscal_year=fiscal_year,
            version_label=version_label,
            effective_from=effective_from,
            effective_to=effective_to,
            snapshot=snapshot,
        )

    def list_versions(self, org_id: str, *, fiscal_year: str | None = None) -> list[dict]:
        return coa_version_repository.list(org_id, fiscal_year=fiscal_year)

    def get_version(self, org_id: str, *, version_id: str) -> dict:
        row = coa_version_repository.get(org_id, version_id=version_id)
        if not row:
            raise ValueError("COA version not found")
        return row

    def resolve_for_reporting(
        self,
        org_id: str,
        *,
        fiscal_period_id: str | None = None,
        coa_version_id: str | None = None,
    ) -> dict | None:
        """Return historical COA snapshot for period-close reporting (ERP-01)."""
        if coa_version_id:
            version = self.get_version(org_id, version_id=coa_version_id)
            snap = version.get("snapshot") if isinstance(version.get("snapshot"), dict) else {}
            return snap or None
        if not fiscal_period_id:
            return None
        from app.modules.erp.fiscal.repositories.fiscal_period_repository import fiscal_period_repository

        period = fiscal_period_repository.get(org_id, period_id=fiscal_period_id)
        if not period:
            return None
        period_end = str(period.get("end_date") or "")
        if not period_end:
            return None
        for version_row in self.list_versions(org_id):
            version = self.get_version(org_id, version_id=str(version_row["id"]))
            effective_from = str(version.get("effective_from") or "")
            effective_to = str(version.get("effective_to") or "") or None
            if not effective_from or period_end < effective_from:
                continue
            if effective_to and period_end > effective_to:
                continue
            snap = version.get("snapshot") if isinstance(version.get("snapshot"), dict) else {}
            if snap:
                return snap
        for version_row in self.list_versions(org_id):
            version = self.get_version(org_id, version_id=str(version_row["id"]))
            snap = version.get("snapshot") if isinstance(version.get("snapshot"), dict) else {}
            if snap:
                return snap
        return None


coa_version_service = CoaVersionService()
