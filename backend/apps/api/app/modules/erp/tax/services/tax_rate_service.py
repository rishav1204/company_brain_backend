from __future__ import annotations

from app.modules.erp.tax.repositories.tax_rate_repository import tax_rate_repository


class TaxRateService:
    def list_rates(self, org_id: str) -> list[dict]:
        return tax_rate_repository.list_active(org_id)

    def create_rate(self, org_id: str, *, hsn_sac: str | None, description: str | None, gst_rate: float, cess_rate: float = 0) -> dict:
        return tax_rate_repository.create(
            org_id, hsn_sac=hsn_sac, description=description, gst_rate=gst_rate, cess_rate=cess_rate
        )

    def resolve_rate(self, org_id: str, *, hsn_sac: str | None, computed_rate: float) -> float:
        return tax_rate_repository.resolve_rate(org_id, hsn_sac=hsn_sac, fallback=computed_rate)


tax_rate_service = TaxRateService()
