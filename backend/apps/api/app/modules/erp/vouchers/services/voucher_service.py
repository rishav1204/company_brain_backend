from __future__ import annotations

from app.modules.core.iam.services.access_control import evaluate_access
from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator
from app.services.db import get_db_conn, set_rls_org
from app.modules.erp.vouchers.constants import EDITABLE_STATUSES, POSTABLE_STATUSES, VOUCHER_TYPES
from app.modules.erp.vouchers.events.voucher_events import (
    emit_voucher_approved,
    emit_voucher_cancelled,
    emit_voucher_created,
    emit_voucher_posted,
    emit_voucher_submitted,
    emit_voucher_validated,
)
from app.modules.erp.vouchers.repositories.voucher_line_repository import voucher_line_repository
from app.modules.erp.vouchers.repositories.voucher_repository import voucher_repository
from app.modules.erp.vouchers.services.journal_generation_service import journal_generation_service
from app.modules.erp.vouchers.services.voucher_sequence_service import voucher_sequence_service
from app.modules.erp.vouchers.services.voucher_validation_service import voucher_validation_service
from app.modules.erp.vouchers.services.voucher_workflow_service import voucher_workflow_service
from app.services.object_context import resolve_object_context


class VoucherService:
    def _total_amount(self, lines: list[dict]) -> float:
        return max(
            sum(float(l.get("debit_amount") or 0) for l in lines),
            sum(float(l.get("credit_amount") or 0) for l in lines),
        )

    def create(
        self,
        org_id: str,
        *,
        voucher_type: str,
        voucher_date: str,
        lines: list[dict],
        narration: str | None = None,
        company_id: str | None = None,
        branch_id: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        created_by: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict | None = None,
        source_module: str = "vouchers",
        generator_payload: dict | None = None,
    ) -> dict:
        vtype = voucher_type.strip().lower()
        if vtype not in VOUCHER_TYPES:
            raise ValueError(f"Invalid voucher_type: {vtype}")
        if idempotency_key:
            existing = voucher_repository.get_by_idempotency(org_id, idempotency_key=idempotency_key)
            if existing:
                return self.get(org_id, voucher_id=str(existing["id"]))

        if not lines and generator_payload:
            from app.modules.erp.vouchers.generators import lines_for_voucher

            lines = lines_for_voucher(org_id, voucher_type=vtype, payload=generator_payload)

        number = voucher_sequence_service.allocate_number(
            org_id, voucher_type=vtype, voucher_date=voucher_date, company_id=company_id
        )
        voucher = voucher_repository.create(
            org_id,
            voucher_number=number,
            voucher_type=vtype,
            voucher_date=voucher_date,
            total_amount=self._total_amount(lines),
            narration=narration,
            company_id=company_id,
            branch_id=branch_id,
            reference_type=reference_type,
            reference_id=reference_id,
            source_module=source_module,
            created_by=created_by,
            idempotency_key=idempotency_key,
            metadata=metadata,
        )
        vid = str(voucher["id"])
        voucher_line_repository.replace_lines(org_id, voucher_id=vid, lines=lines)
        emit_voucher_created(org_id, vid, voucher_type=vtype)
        self._audit(org_id, voucher_id=vid, action="voucher.created", actor_id=created_by)
        return self.get(org_id, voucher_id=vid)

    def get(self, org_id: str, *, voucher_id: str) -> dict:
        voucher = voucher_repository.get(org_id, voucher_id=voucher_id)
        if not voucher:
            raise ValueError("Voucher not found")
        lines = voucher_line_repository.list_by_voucher(org_id, voucher_id=voucher_id)
        return {"voucher": voucher, "lines": lines}

    def list(
        self,
        org_id: str,
        *,
        voucher_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
        branch_ids: list[str] | None = None,
    ) -> list[dict]:
        return voucher_repository.list(
            org_id,
            voucher_type=voucher_type,
            status=status,
            limit=limit,
            offset=offset,
            branch_ids=branch_ids,
        )

    def validate(self, org_id: str, *, voucher_id: str) -> dict:
        item = self.get(org_id, voucher_id=voucher_id)
        voucher_validation_service.validate(org_id, voucher=item["voucher"], lines=item["lines"])
        voucher_repository.set_status(org_id, voucher_id=voucher_id, status="validated")
        emit_voucher_validated(org_id, voucher_id)
        return self.get(org_id, voucher_id=voucher_id)

    def submit_for_approval(self, org_id: str, *, voucher_id: str, submitted_by: str) -> dict:
        item = self.get(org_id, voucher_id=voucher_id)
        if str(item["voucher"]["status"]) not in {"draft", "validated"}:
            raise ValueError("Voucher cannot be submitted in current status")
        voucher_validation_service.validate(org_id, voucher=item["voucher"], lines=item["lines"])
        wf = voucher_workflow_service.start(
            org_id,
            voucher_id=voucher_id,
            amount=float(item["voucher"].get("total_amount") or 0),
            started_by=submitted_by,
        )
        workflow_id = str((wf or {}).get("workflow_id") or (wf or {}).get("id") or "")
        voucher_repository.set_status(
            org_id, voucher_id=voucher_id, status="pending_approval", workflow_id=workflow_id or None
        )
        emit_voucher_submitted(org_id, voucher_id)
        return self.get(org_id, voucher_id=voucher_id)

    def approve(
        self,
        org_id: str,
        *,
        voucher_id: str,
        approver_id: str,
        auto_post: bool = False,
        generator_payload: dict | None = None,
    ) -> dict:
        item = self.get(org_id, voucher_id=voucher_id)
        status = str(item["voucher"]["status"])
        if status not in {"validated", "pending_approval", "draft"}:
            raise ValueError(f"Cannot approve voucher in status={status}")

        obj = resolve_object_context(org_id=org_id, object_type="voucher", object_id=voucher_id)
        obj.amount = float(item["voucher"].get("total_amount") or 0)
        decision = evaluate_access(
            org_id=org_id,
            user_id=approver_id,
            roles=[],
            action="voucher.approve",
            object_context=obj,
        )
        if not decision.allowed:
            raise ValueError(decision.reason or "Voucher approval denied")

        gen = None
        post_result = None
        if auto_post:
            with get_db_conn() as conn:
                set_rls_org(conn, org_id)
                voucher_repository.set_status_conn(
                    conn, org_id, voucher_id=voucher_id, status="approved", approved_by=approver_id
                )
                gen = journal_generation_service.generate_with_conn(
                    conn,
                    org_id,
                    voucher_id=voucher_id,
                    approver_id=approver_id,
                    generator_payload=generator_payload,
                )
                journal_id = str(gen["journal_id"])
                post_result = posting_orchestrator.post_journal_with_conn(
                    conn, org_id, journal_id=journal_id, posted_by=approver_id, defer_side_effects=True
                )
                voucher_repository.set_status_conn(
                    conn, org_id, voucher_id=voucher_id, status="posted", posted_by=approver_id
                )
            if gen and gen.get("journal"):
                posting_orchestrator._emit_post_side_effects(
                    org_id,
                    journal_id=str(gen["journal_id"]),
                    journal=gen["journal"]["journal"],
                    batch_id=str((post_result or {}).get("ledger_batch_id") or ""),
                    posted_by=approver_id,
                )
            emit_voucher_approved(org_id, voucher_id)
            self._audit(org_id, voucher_id=voucher_id, action="voucher.approved", actor_id=approver_id)
            emit_voucher_posted(org_id, voucher_id, journal_id=str(gen["journal_id"]))
            self._audit(org_id, voucher_id=voucher_id, action="voucher.posted", actor_id=approver_id)
            result = {
                "voucher": self.get(org_id, voucher_id=voucher_id),
                "journal": {"voucher_id": voucher_id, "journal_id": gen["journal_id"], "status": "journal_generated"},
                "post_result": post_result,
            }
            return result

        voucher_repository.set_status(org_id, voucher_id=voucher_id, status="approved", approved_by=approver_id)
        emit_voucher_approved(org_id, voucher_id)
        self._audit(org_id, voucher_id=voucher_id, action="voucher.approved", actor_id=approver_id)

        gen = journal_generation_service.generate(
            org_id,
            voucher_id=voucher_id,
            approver_id=approver_id,
            generator_payload=generator_payload,
        )
        result = {"voucher": self.get(org_id, voucher_id=voucher_id), "journal": gen}
        return result

    def generate_journal(
        self,
        org_id: str,
        *,
        voucher_id: str,
        approver_id: str,
        generator_payload: dict | None = None,
    ) -> dict:
        item = self.get(org_id, voucher_id=voucher_id)
        status = str(item["voucher"]["status"])
        if status not in {"approved", "validated", "pending_approval", "draft"}:
            raise ValueError(f"Cannot generate journal for voucher in status={status}")
        gen = journal_generation_service.generate(
            org_id,
            voucher_id=voucher_id,
            approver_id=approver_id,
            generator_payload=generator_payload,
        )
        return {"voucher": self.get(org_id, voucher_id=voucher_id), "journal": gen}

    def post(self, org_id: str, *, voucher_id: str, posted_by: str) -> dict:
        item = self.get(org_id, voucher_id=voucher_id)
        status = str(item["voucher"]["status"])
        journal_id = str(item["voucher"].get("journal_id") or "")
        if status not in POSTABLE_STATUSES and status != "posted":
            raise ValueError(f"Cannot post voucher in status={status}")
        if not journal_id:
            raise ValueError("Voucher has no linked journal")

        post_result = None
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            post_result = posting_orchestrator.post_journal_with_conn(
                conn, org_id, journal_id=journal_id, posted_by=posted_by, defer_side_effects=True
            )
            voucher_repository.set_status_conn(
                conn, org_id, voucher_id=voucher_id, status="posted", posted_by=posted_by
            )

        from app.modules.erp.journals.repositories.journal_repository import journal_repository

        journal_row = journal_repository.get(org_id, journal_id=journal_id) or {}
        posting_orchestrator._emit_post_side_effects(
            org_id,
            journal_id=journal_id,
            journal=journal_row,
            batch_id=str((post_result or {}).get("ledger_batch_id") or ""),
            posted_by=posted_by,
        )
        emit_voucher_posted(org_id, voucher_id, journal_id=journal_id)
        self._audit(org_id, voucher_id=voucher_id, action="voucher.posted", actor_id=posted_by)
        return post_result

    def cancel(self, org_id: str, *, voucher_id: str, actor_id: str | None = None) -> dict:
        item = self.get(org_id, voucher_id=voucher_id)
        if str(item["voucher"]["status"]) not in EDITABLE_STATUSES:
            raise ValueError("Voucher cannot be cancelled")
        voucher_repository.set_status(org_id, voucher_id=voucher_id, status="cancelled")
        emit_voucher_cancelled(org_id, voucher_id)
        self._audit(org_id, voucher_id=voucher_id, action="voucher.cancelled", actor_id=actor_id)
        return self.get(org_id, voucher_id=voucher_id)

    def reverse(self, org_id: str, *, voucher_id: str, reversed_by: str) -> dict:
        item = self.get(org_id, voucher_id=voucher_id)
        if str(item["voucher"]["status"]) != "posted":
            raise ValueError("Only posted vouchers can be reversed")
        journal_id = str(item["voucher"].get("journal_id") or "")
        if not journal_id:
            raise ValueError("Voucher has no linked journal")
        from app.modules.erp.journals.services.reversal_service import journal_reversal_service

        rev = journal_reversal_service.reverse(
            org_id, journal_id=journal_id, reversed_by=reversed_by, approver_id=reversed_by
        )
        voucher_repository.set_status(org_id, voucher_id=voucher_id, status="reversed")
        from app.modules.erp.vouchers.events.voucher_events import emit_voucher_reversed

        emit_voucher_reversed(org_id, voucher_id, reversal_journal_id=str(rev.get("reversal_journal_id") or ""))
        self._audit(org_id, voucher_id=voucher_id, action="voucher.reversed", actor_id=reversed_by)
        return {"voucher": self.get(org_id, voucher_id=voucher_id), "reversal": rev}

    def create_from_extraction(self, org_id: str, *, extraction_id: str, created_by: str | None = None) -> dict:
        from app.modules.erp.ports.intelligence_registry import intelligence_registry

        intel = intelligence_registry.invoice()
        extraction = intel.get_extraction(org_id, extraction_id)
        if not extraction:
            raise ValueError("Extraction not found")
        meta = extraction.get("metadata") if isinstance(extraction.get("metadata"), dict) else {}
        expense_id = meta.get("expense_account_id")
        payable_id = meta.get("payable_account_id")
        for pred in intel.list_predictions_for_extraction(org_id, extraction_id):
            if pred.get("prediction_type") == "expense_account" and not expense_id:
                expense_id = pred.get("suggested_account_id")
            if pred.get("prediction_type") == "payable_account" and not payable_id:
                payable_id = pred.get("suggested_account_id")
        taxable = float(extraction.get("taxable_amount") or 0)
        gst = float(extraction.get("gst_amount") or 0)
        total = float(extraction.get("total_amount") or 0)
        lines_payload = {
            "expense_account_id": expense_id,
            "payable_account_id": payable_id,
            "invoice_amount": taxable or max(total - gst, 0),
            "gst_amount": gst,
            "total_amount": total,
            "company_id": meta.get("company_id"),
        }
        if not lines_payload["expense_account_id"] or not lines_payload["payable_account_id"]:
            raise ValueError("Extraction missing account mapping for purchase voucher")
        from app.modules.erp.vouchers.generators import lines_for_voucher

        lines = lines_for_voucher(org_id, voucher_type="purchase", payload=lines_payload)
        voucher_date = str(extraction.get("invoice_date") or extraction.get("created_at") or "")[:10]
        if len(voucher_date) < 10:
            from datetime import date

            voucher_date = date.today().isoformat()
        return self.create(
            org_id,
            voucher_type="purchase",
            voucher_date=voucher_date,
            lines=lines,
            narration=extraction.get("vendor_name") or "AI draft purchase voucher",
            company_id=meta.get("company_id"),
            created_by=created_by,
            idempotency_key=f"ai-extraction:{extraction_id}",
            metadata={"ai_extraction_id": extraction_id, "document_id": extraction.get("document_id")},
            generator_payload=lines_payload,
            source_module="invoice_ai",
        )

    def _audit(self, org_id: str, *, voucher_id: str, action: str, actor_id: str | None) -> None:
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id,
                actor_type="user",
                actor_id=actor_id or "erp.vouchers",
                action=action,
                object_ref=f"erp:voucher:{voucher_id}",
                entity_type="voucher",
                entity_id=voucher_id,
                source_service="erp.vouchers",
            )
        except Exception:
            pass


voucher_service = VoucherService()
