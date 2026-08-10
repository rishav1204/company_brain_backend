from __future__ import annotations

from app.modules.erp.gl.repositories.ledger_query_repository import ledger_query_repository


class LedgerService:
    def list_entries(
        self,
        org_id: str,
        *,
        account_id: str | None = None,
        batch_id: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        branch_ids: list[str] | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict]:
        return ledger_query_repository.list_entries(
            org_id,
            account_id=account_id,
            batch_id=batch_id,
            reference_type=reference_type,
            reference_id=reference_id,
            branch_ids=branch_ids,
            limit=limit,
            offset=offset,
        )


ledger_service = LedgerService()

