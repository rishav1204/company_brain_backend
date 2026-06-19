from __future__ import annotations

from app.modules.erp.banking.repositories.bank_account_repository import bank_account_repository
from app.modules.erp.treasury.engine.transfer_engine import approval_roles_for_amount, validate_transfer
from app.modules.erp.treasury.repositories.transfer_repository import transfer_repository


class TransferService:
    def create(
        self,
        org_id: str,
        *,
        source_account_id: str,
        destination_account_id: str,
        transfer_amount: float,
        transfer_date: str,
        created_by: str | None = None,
    ) -> dict:
        validate_transfer(source_account_id=source_account_id, destination_account_id=destination_account_id, amount=transfer_amount)
        row = transfer_repository.create(
            org_id,
            source_account_id=source_account_id,
            destination_account_id=destination_account_id,
            transfer_amount=transfer_amount,
            transfer_date=transfer_date,
            status="pending_approval",
            metadata={"created_by": created_by, "required_roles": approval_roles_for_amount(transfer_amount)},
        )
        self._start_workflow(org_id, transfer_id=str(row["id"]))
        return row

    def list(self, org_id: str, *, status: str | None = None) -> list[dict]:
        return transfer_repository.list(org_id, status=status)

    def get(self, org_id: str, *, transfer_id: str) -> dict | None:
        return transfer_repository.get(org_id, transfer_id=transfer_id)

    def approve_and_execute(self, org_id: str, *, transfer_id: str, approved_by: str) -> dict:
        row = transfer_repository.get(org_id, transfer_id=transfer_id)
        if not row:
            raise ValueError("Transfer not found")
        if str(row.get("status")) not in {"draft", "pending_approval", "approved"}:
            raise ValueError(f"Cannot execute transfer in status {row.get('status')}")

        from app.modules.erp.fiscal.services.posting_validation_service import posting_validation_service

        posting_validation_service.validate_period_open(org_id, str(row["transfer_date"])[:10], actor_id=approved_by)

        transfer_repository.set_status(org_id, transfer_id=transfer_id, status="processing", approved_by=approved_by)
        src = bank_account_repository.get(org_id, bank_account_id=str(row["source_account_id"]))
        dest = bank_account_repository.get(org_id, bank_account_id=str(row["destination_account_id"]))
        if not src or not dest:
            raise ValueError("Source or destination account not found")

        from app.modules.erp.banking.services.payment_execution_service import payment_execution_service

        amount = float(row["transfer_amount"])
        req = payment_execution_service.create_request(
            org_id,
            payment_type="internal_transfer",
            beneficiary_type="internal",
            beneficiary_ref=str(row["destination_account_id"]),
            bank_account_id=str(row["source_account_id"]),
            amount=amount,
            currency_code="INR",
            scheduled_date=str(row["transfer_date"])[:10],
            source_type="inter_account_transfer",
            source_id=transfer_id,
            company_id=None,
            created_by=approved_by,
            metadata={"dest_bank_account_id": str(row["destination_account_id"])},
            start_workflow=False,
        )
        pr_id = str(req.get("id") or "")
        payment_execution_service.mark_workflow_approved(org_id, payment_request_id=pr_id, approver_id=approved_by)
        result = payment_execution_service.execute_payment(org_id, payment_request_id=pr_id, auto_post=True)
        transfer_repository.set_status(org_id, transfer_id=transfer_id, status="completed", payment_request_id=pr_id, approved_by=approved_by)
        from app.modules.erp.treasury.services.cash_position_service import cash_position_service

        cash_position_service.refresh_and_emit(org_id)
        return {"transfer": row, "payment_request_id": pr_id, "execution": result}

    def cancel(self, org_id: str, *, transfer_id: str) -> dict:
        row = transfer_repository.get(org_id, transfer_id=transfer_id)
        if not row:
            raise ValueError("Transfer not found")
        if str(row.get("status")) in {"completed", "processing"}:
            raise ValueError("Cannot cancel completed transfer")
        return transfer_repository.set_status(org_id, transfer_id=transfer_id, status="cancelled")

    def _start_workflow(self, org_id: str, *, transfer_id: str) -> None:
        try:
            from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

            handle_entity_created(
                org_id=org_id,
                payload={
                    "entity_type": "treasury_transfer",
                    "entity_id": transfer_id,
                    "workflow_key": "TREASURY_TRANSFER_APPROVAL",
                    "metadata": {"transfer_id": transfer_id},
                },
            )
        except Exception:
            pass


transfer_service = TransferService()
