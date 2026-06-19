from __future__ import annotations

from datetime import date, timedelta

from app.modules.erp.compliance.repositories.compliance_repository import compliance_rule_repository, compliance_type_repository


class ComplianceRuleService:
    def list_types(self) -> list[dict]:
        return compliance_type_repository.list_active()

    def list_rules(self, org_id: str) -> list[dict]:
        return compliance_rule_repository.list(org_id)

    def upsert_rule(self, org_id: str, *, compliance_code: str, **fields) -> dict:
        ctype = compliance_type_repository.get_by_code(compliance_code)
        if not ctype:
            raise ValueError(f"Unknown compliance type: {compliance_code}")
        return compliance_rule_repository.upsert(org_id, compliance_type_id=ctype["id"], **fields)

    def seed_defaults(self, org_id: str) -> dict:
        count = compliance_rule_repository.seed_defaults_for_org(org_id)
        return {"seeded": count}


compliance_rule_service = ComplianceRuleService()
