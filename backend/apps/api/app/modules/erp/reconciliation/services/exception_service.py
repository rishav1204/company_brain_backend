from __future__ import annotations

from app.modules.erp.reconciliation.events.reconciliation_events import emit_reconciliation_exception_created
from app.modules.erp.reconciliation.repositories.exception_repository import exception_repository


class ExceptionService:
    def create(
        self,
        org_id: str,
        *,
        bank_transaction_id: str | None,
        reconciliation_id: str | None,
        exception_type: str,
        description: str,
        metadata: dict | None = None,
    ) -> dict:
        row = exception_repository.create(
            org_id,
            bank_transaction_id=bank_transaction_id,
            reconciliation_id=reconciliation_id,
            exception_type=exception_type,
            description=description,
            metadata=metadata,
        )
        emit_reconciliation_exception_created(
            org_id,
            exception_id=str(row["id"]),
            exception_type=exception_type,
            bank_transaction_id=bank_transaction_id,
        )
        return row

    def list(self, org_id: str, *, status: str | None = "open") -> list[dict]:
        return exception_repository.list(org_id, status=status)

    def assign(self, org_id: str, *, exception_id: str, assigned_to: str) -> dict:
        return exception_repository.assign(org_id, exception_id=exception_id, assigned_to=assigned_to)


exception_service = ExceptionService()
