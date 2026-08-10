"""
ERP-owned ACL for intelligence implementations living in Finance OS.

Finance OS may import `app.modules.erp.query_services` only. Domain math
(aging, discounts, matching, liquidity buckets) and the reads that domain
intelligence needs are exposed here so the calculations stay ERP-owned and
are never duplicated inside Finance OS.
"""

from __future__ import annotations

from datetime import date
from typing import Any


class DomainCalc:
    """Pure ERP domain calculators exposed to Finance OS intelligence."""

    def ap_aging_days(self, *, due_date: str, as_of: str | None = None) -> int:
        from app.modules.erp.accounts_payable.engine.aging_engine import aging_days

        return aging_days(due_date=due_date, as_of=as_of)

    def ar_aging_days(self, *, due_date: str, as_of: str | None = None) -> int:
        from app.modules.erp.accounts_receivable.engine.aging_engine import aging_days

        return aging_days(due_date=due_date, as_of=as_of)

    def compute_discount(self, *, invoice_amount: float, discount_rate: float) -> float:
        from app.modules.erp.accounts_payable.engine.payment_engine import compute_discount

        return compute_discount(invoice_amount=invoice_amount, discount_rate=discount_rate)

    def collection_probability(self, *, aging_days: int, risk_score: float) -> float:
        from app.modules.erp.accounts_receivable.engine.collection_engine import collection_probability

        return collection_probability(aging_days=aging_days, risk_score=risk_score)

    def bucket_cashflows(self, *, inflows: list[dict], outflows: list[dict], as_of: date | None = None) -> dict:
        from app.modules.erp.treasury.engine.liquidity_engine import bucket_cashflows

        return bucket_cashflows(inflows=inflows, outflows=outflows, as_of=as_of)

    def detect_treasury_risks(self, **kwargs: Any) -> list[dict]:
        from app.modules.erp.treasury.engine.risk_engine import detect_treasury_risks

        return detect_treasury_risks(**kwargs)

    def detect_reconciliation_anomalies(
        self,
        *,
        bank_tx: dict,
        candidates: list[dict] | None = None,
        history_amounts: list[float] | None = None,
    ) -> list[dict]:
        from app.modules.erp.reconciliation.engine.anomaly_engine import detect_reconciliation_anomalies

        return detect_reconciliation_anomalies(
            bank_tx=bank_tx,
            candidates=candidates,
            history_amounts=history_amounts,
        )

    def rank_all_candidates(
        self,
        bank_tx: dict,
        ledger_entries: list[dict],
        subledger_candidates: list[dict],
        *,
        rules: list[dict] | None = None,
    ) -> list[dict]:
        from app.modules.erp.reconciliation.engine.matching_engine import rank_all_candidates

        return rank_all_candidates(bank_tx, ledger_entries, subledger_candidates, rules=rules)

    def validate_gstin(self, gstin: str) -> Any:
        """Raises ValueError when invalid — ERP remains the authority on GSTIN format."""
        from app.modules.erp.tax.validators.gstin_validator import validate_gstin

        return validate_gstin(gstin)

    def gstin_error(self, gstin: str) -> str | None:
        """Non-raising helper: returns the validation message when GSTIN is invalid."""
        try:
            self.validate_gstin(gstin)
        except ValueError as exc:
            return str(exc)
        return None


class IntelReads:
    """Repository reads required by relocated domain intelligence."""

    def list_accounts(self, org_id: str, *, limit: int = 2000) -> list[dict]:
        from app.modules.erp.coa.repositories.account_repository import account_repository

        return account_repository.list(org_id, limit=limit)

    def list_item_movements(self, org_id: str, *, item_id: str, limit: int = 365) -> list[dict]:
        from app.modules.erp.inventory.repositories.movement_repository import movement_repository

        return movement_repository.list(org_id, item_id=item_id, limit=limit)

    def list_stock_balances(self, org_id: str, *, limit: int = 2000) -> list[dict]:
        from app.modules.erp.inventory.repositories.movement_repository import balance_repository

        return balance_repository.list_all(org_id, limit=limit)

    def list_items(self, org_id: str, *, limit: int = 2000) -> list[dict]:
        from app.modules.erp.inventory.repositories.item_repository import item_repository

        return item_repository.list(org_id, limit=limit)

    def list_expense_claims(self, org_id: str, *, employee_id: str | None = None, limit: int = 500) -> list[dict]:
        from app.modules.erp.expenses.repositories.claim_repository import claim_repository

        return claim_repository.list(org_id, employee_id=employee_id, limit=limit)

    def list_purchase_orders(self, org_id: str, *, limit: int = 500) -> list[dict]:
        from app.modules.erp.procurement.repositories.po_repository import po_repository

        return po_repository.list(org_id, limit=limit)

    def recommend_vendors(self, org_id: str, *, item_hint: str = "", limit: int = 5) -> list[dict]:
        from app.modules.erp.procurement.services.vendor_selection_service import vendor_selection_service

        return vendor_selection_service.recommend(org_id, item_hint=item_hint, limit=limit)


domain_calc = DomainCalc()
intel_reads = IntelReads()
