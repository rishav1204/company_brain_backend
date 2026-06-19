from __future__ import annotations

from app.modules.erp.tax.engine.itc_engine import build_itc_rows, evaluate_itc_eligibility
from app.modules.erp.tax.repositories.itc_repository import itc_blocked_rules_repository, itc_ledger_repository


class ItcService:
    def create_from_purchase(self, org_id: str, *, gst_transaction_id: str, gst_transaction: dict) -> list[dict]:
        blocked = itc_blocked_rules_repository.list_active(org_id)
        itc_eligible = True
        try:
            from app.modules.erp.coa.repositories.mapping_repository import mapping_repository

            mappings = mapping_repository.list_gst_mappings(org_id)
            itc_eligible = any(m.get("itc_eligible") for m in mappings if "input" in str(m.get("gst_type", "")))
        except Exception:
            pass
        rows = []
        for itc_type, amount_key in [("CGST", "cgst_amount"), ("SGST", "sgst_amount"), ("IGST", "igst_amount")]:
            amount = float(gst_transaction.get(amount_key) or 0)
            if amount <= 0:
                continue
            el = evaluate_itc_eligibility(
                itc_type=itc_type,
                amount=amount,
                blocked_rules=blocked,
                itc_eligible_mapping=itc_eligible,
            )
            for r in build_itc_rows(gst_transaction, [el]):
                row = itc_ledger_repository.create(org_id, gst_transaction_id=gst_transaction_id, **r)
                rows.append(row)
        return rows

    def list_ledger(self, org_id: str, *, status: str | None = None) -> list[dict]:
        return itc_ledger_repository.list(org_id, status=status)

    def claim(self, org_id: str, *, itc_id: str, claimed_amount: float, actor_id: str) -> dict:
        return itc_ledger_repository.claim(org_id, itc_id=itc_id, claimed_amount=claimed_amount)

    def summary(self, org_id: str, *, return_period: str | None = None) -> dict:
        return itc_ledger_repository.summary_by_period(org_id, return_period=return_period)


itc_service = ItcService()
