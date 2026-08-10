from __future__ import annotations

from app.modules.erp.banking.repositories.bank_account_repository import bank_account_repository
from app.modules.erp.banking.repositories.bank_transaction_repository import bank_transaction_repository
from app.modules.erp.gl.repositories.ledger_query_repository import ledger_query_repository
from app.modules.erp.ports.intelligence_registry import intelligence_registry
from app.modules.erp.reconciliation.repositories.rules_repository import rules_repository


class BankMatchService:
    def collect_candidates(self, org_id: str, bank_tx: dict) -> tuple[list[dict], list[dict]]:
        acct = bank_account_repository.get(org_id, bank_account_id=str(bank_tx["bank_account_id"]))
        ledger_entries: list[dict] = []
        if acct and acct.get("ledger_account_id"):
            ledger_entries = ledger_query_repository.list_entries(
                org_id, account_id=str(acct["ledger_account_id"]), limit=100
            )
        from app.modules.erp.reconciliation.services.customer_match_service import customer_match_service
        from app.modules.erp.reconciliation.services.vendor_match_service import vendor_match_service

        subledger = vendor_match_service.collect_candidates(org_id) + customer_match_service.collect_candidates(org_id)
        return ledger_entries, subledger

    def rank_for_transaction(self, org_id: str, bank_tx: dict, *, limit: int = 5) -> list[dict]:
        ledger_entries, subledger = self.collect_candidates(org_id, bank_tx)
        rules = rules_repository.list_active(org_id)
        return intelligence_registry.reconciliation().suggest_matches(
            bank_tx,
            ledger_entries,
            subledger_candidates=subledger,
            rules=rules,
            limit=limit,
        )

    def list_workbench(self, org_id: str, *, bank_account_id: str | None = None, limit: int = 100) -> dict:
        unreconciled = bank_transaction_repository.list(
            org_id, bank_account_id=bank_account_id, reconciliation_status="unreconciled", limit=limit
        )
        suggested = bank_transaction_repository.list(
            org_id, bank_account_id=bank_account_id, reconciliation_status="suggested", limit=limit
        )
        matched = bank_transaction_repository.list(
            org_id, bank_account_id=bank_account_id, reconciliation_status="matched", limit=limit
        )
        return {"unreconciled": unreconciled, "suggested": suggested, "matched": matched}


bank_match_service = BankMatchService()
