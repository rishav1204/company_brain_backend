from __future__ import annotations

from app.modules.erp.coa.repositories.mapping_repository import mapping_repository
from app.modules.erp.coa.services.account_validation_service import account_validation_service


class MappingService:
    def create_financial_mapping(
        self,
        org_id: str,
        *,
        account_id: str,
        statement_type: str,
        reporting_category: str,
        company_id: str | None = None,
    ) -> dict:
        account_validation_service.validate_statement_mapping(
            statement_type=statement_type, reporting_category=reporting_category
        )
        row = mapping_repository.create_financial_mapping(
            org_id,
            account_id=account_id,
            statement_type=statement_type,
            reporting_category=reporting_category,
            company_id=company_id,
        )
        return row

    def list_financial_mappings(self, org_id: str, *, company_id: str | None = None) -> list[dict]:
        return mapping_repository.list_financial_mappings(org_id, company_id=company_id)

    def delete_financial_mapping(self, org_id: str, *, mapping_id: str) -> dict:
        return mapping_repository.delete_financial_mapping(org_id, mapping_id=mapping_id)

    def create_gst_mapping(
        self,
        org_id: str,
        *,
        account_id: str,
        gst_type: str,
        itc_eligible: bool,
        company_id: str | None = None,
    ) -> dict:
        account_validation_service.validate_gst_mapping(gst_type=gst_type, itc_eligible=bool(itc_eligible))
        row = mapping_repository.create_gst_mapping(
            org_id,
            account_id=account_id,
            gst_type=gst_type,
            itc_eligible=bool(itc_eligible),
            company_id=company_id,
        )
        try:
            from app.modules.erp.coa.events.coa_events import emit_gst_mapping_updated

            emit_gst_mapping_updated(org_id, account_id=account_id, gst_type=gst_type)
        except Exception:
            pass
        return row

    def list_gst_mappings(self, org_id: str, *, company_id: str | None = None) -> list[dict]:
        return mapping_repository.list_gst_mappings(org_id, company_id=company_id)

    def delete_gst_mapping(self, org_id: str, *, mapping_id: str) -> dict:
        return mapping_repository.delete_gst_mapping(org_id, mapping_id=mapping_id)


mapping_service = MappingService()

