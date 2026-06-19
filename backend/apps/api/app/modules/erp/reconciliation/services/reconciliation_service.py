from __future__ import annotations

from app.modules.erp.banking.repositories.bank_transaction_repository import bank_transaction_repository
from app.modules.erp.reconciliation.engine.settlement_engine import build_match_lines
from app.modules.erp.reconciliation.events.reconciliation_events import emit_reconciliation_suggested
from app.modules.erp.reconciliation.repositories.match_line_repository import match_line_repository
from app.modules.erp.reconciliation.repositories.reconciliation_repository import reconciliation_repository
from app.modules.erp.reconciliation.services.approval_service import approval_service
from app.modules.erp.reconciliation.services.bank_match_service import bank_match_service
from app.modules.erp.reconciliation.services.exception_service import exception_service
from app.modules.erp.reconciliation.validators.match_validator import validate_confidence_for_auto_suggest, validate_match_request


class ReconciliationService:
    def suggest_matches(self, org_id: str, *, bank_account_id: str | None = None, limit: int = 50) -> list[dict]:
        txs = bank_transaction_repository.list(
            org_id, bank_account_id=bank_account_id, reconciliation_status="unreconciled", limit=limit
        )
        created: list[dict] = []
        for tx in txs:
            suggestions = bank_match_service.rank_for_transaction(org_id, tx, limit=3)
            for sug in suggestions:
                if not validate_confidence_for_auto_suggest(sug["confidence_score"]):
                    continue
                band = sug.get("band", "manual")
                status = "pending_approval" if band == "review" else "suggested"
                meta = {
                    "factors": sug.get("factors"),
                    "explanation": sug.get("explanation"),
                    "match_target_type": sug.get("match_target_type"),
                    "match_target_id": sug.get("match_target_id"),
                    "band": band,
                }
                row = reconciliation_repository.create(
                    org_id,
                    bank_transaction_id=str(tx["id"]),
                    ledger_entry_id=sug.get("ledger_entry_id"),
                    match_type=sug.get("match_type", "suggested"),
                    confidence_score=sug["confidence_score"],
                    status=status,
                    matched_entity_type=sug.get("match_target_type"),
                    matched_entity_id=sug.get("match_target_id"),
                    metadata=meta,
                )
                bank_transaction_repository.set_reconciliation_status(
                    org_id, transaction_id=str(tx["id"]), status=status
                )
                created.append(row)
                emit_reconciliation_suggested(org_id, reconciliation_id=str(row.get("id")), confidence=sug["confidence_score"])
                if sug["confidence_score"] < 0.6 or sug.get("match_type") == "exception":
                    self._start_workflow(org_id, reconciliation_id=str(row.get("id")))
                try:
                    from app.modules.platform.events.events.ai_events import emit_reconciliation_suggested as emit_ai

                    if sug["confidence_score"] >= 0.7:
                        emit_ai(org_id, entity_id=str(row.get("id")), summary=sug.get("explanation") or "")
                except Exception:
                    pass
        return created

    def manual_match(
        self,
        org_id: str,
        *,
        bank_transaction_ids: list[str],
        entity_allocations: list[dict],
        ledger_entry_id: str | None = None,
        actor_id: str | None = None,
    ) -> dict:
        validate_match_request(bank_transaction_ids=bank_transaction_ids, allocations=entity_allocations)
        primary_tx = bank_transaction_ids[0]
        row = reconciliation_repository.create(
            org_id,
            bank_transaction_id=primary_tx,
            ledger_entry_id=ledger_entry_id,
            match_type="suggested",
            confidence_score=1.0,
            status="pending_approval",
            matched_entity_type=str(entity_allocations[0].get("entity_type")),
            matched_entity_id=str(entity_allocations[0].get("entity_id")),
            metadata={"manual": True, "created_by": actor_id},
        )
        rid = str(row["id"])
        lines = build_match_lines(
            reconciliation_id=rid,
            bank_transaction_id=primary_tx,
            allocations=entity_allocations,
        )
        match_line_repository.create_batch(org_id, lines)
        for tx_id in bank_transaction_ids:
            bank_transaction_repository.set_reconciliation_status(org_id, transaction_id=tx_id, status="pending_approval")
        return {"reconciliation_id": rid, "match_lines": len(lines)}

    def list_suggestions(self, org_id: str, *, status: str | None = "suggested") -> list[dict]:
        return reconciliation_repository.list(org_id, status=status)

    def approve_match(self, org_id: str, *, reconciliation_id: str, approved_by: str, ledger_entry_id: str | None = None, roles: list[str] | None = None) -> dict:
        return approval_service.approve(
            org_id, reconciliation_id=reconciliation_id, approved_by=approved_by, ledger_entry_id=ledger_entry_id, roles=roles
        )

    def reject_match(self, org_id: str, *, reconciliation_id: str, actor_id: str) -> dict:
        return approval_service.reject(org_id, reconciliation_id=reconciliation_id, actor_id=actor_id)

    def escalate_to_manual_review(self, org_id: str, *, reconciliation_id: str, actor_id: str) -> dict:
        row = reconciliation_repository.get(org_id, reconciliation_id=reconciliation_id)
        if not row:
            raise ValueError("Reconciliation not found")
        result = reconciliation_repository.set_status(org_id, reconciliation_id=reconciliation_id, status="manual_review")
        self._start_workflow(org_id, reconciliation_id=reconciliation_id)
        exception_service.create(
            org_id,
            bank_transaction_id=str(row.get("bank_transaction_id")),
            reconciliation_id=reconciliation_id,
            exception_type="manual_review",
            description="Escalated to manual review",
        )
        return result

    def run_daily_suggestions(self, org_id: str) -> dict:
        items = self.suggest_matches(org_id)
        return {"suggestions_created": len(items)}

    def suggest_for_account(self, org_id: str, *, bank_account_id: str) -> dict:
        items = self.suggest_matches(org_id, bank_account_id=bank_account_id, limit=30)
        return {"suggestions_created": len(items)}

    def _start_workflow(self, org_id: str, *, reconciliation_id: str) -> None:
        try:
            from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

            handle_entity_created(
                org_id=org_id,
                payload={
                    "entity_type": "reconciliation",
                    "entity_id": reconciliation_id,
                    "workflow_key": "BANK_RECONCILIATION",
                    "metadata": {"reconciliation_id": reconciliation_id},
                },
            )
        except Exception:
            pass


reconciliation_service = ReconciliationService()
