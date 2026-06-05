from __future__ import annotations



from app.modules.core.iam.services.maker_checker_service import MakerCheckerViolation, enforce_maker_checker

from app.modules.erp.journals.events.journal_events import emit_journal_reversed

from app.modules.erp.journals.repositories.journal_line_repository import journal_line_repository

from app.modules.erp.journals.repositories.journal_repository import journal_repository

from app.modules.erp.journals.repositories.reversal_repository import reversal_repository

from app.modules.erp.journals.services.approval_service import approval_service

from app.modules.erp.journals.services.journal_service import journal_service

from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator

from app.modules.erp.journals.validators.reversal_validator import reversal_validator

from app.services.metrics import metrics_store





class JournalReversalService:

    def reverse(

        self,

        org_id: str,

        *,

        journal_id: str,

        reversed_by: str | None,

        reversal_reason: str | None = None,

        approver_id: str | None = None,

    ) -> dict:

        original = journal_repository.get(org_id, journal_id=journal_id)

        if not original:

            raise ValueError("Journal not found")

        reversal_validator.ensure_reversible(str(original.get("journal_status")))



        existing = reversal_repository.get_by_original(org_id, original_journal_id=journal_id)

        if existing:

            return {

                "original_journal_id": journal_id,

                "reversal_journal_id": existing.get("reversal_journal_id"),

                "idempotent": True,

            }



        try:

            enforce_maker_checker(

                created_by=str(original.get("created_by") or ""),

                actor_user_id=str(reversed_by or ""),

                org_id=org_id,

            )

        except MakerCheckerViolation as exc:

            raise ValueError(str(exc)) from exc



        original_lines = journal_line_repository.list_by_journal(org_id, journal_id=journal_id)

        reversed_lines = [

            {

                "account_id": line["account_id"],

                "debit_amount": float(line.get("credit_amount") or 0),

                "credit_amount": float(line.get("debit_amount") or 0),

                "line_description": f"Reversal: {line.get('line_description') or ''}".strip(),

                "cost_center_id": line.get("cost_center_id"),

                "tax_code": line.get("tax_code"),

                "reference_type": "journal",

                "reference_id": journal_id,

            }

            for line in original_lines

        ]



        reversal_journal = journal_service.create_draft(

            org_id,

            created_by=None,

            journal_type="reversal",

            posting_date=str(original.get("posting_date")),

            description=f"Reversal of {original.get('journal_number')}: {reversal_reason or ''}".strip(),

            source_type="journal_reversal",

            source_id=journal_id,

            currency_code=str(original.get("currency_code") or "INR"),

            exchange_rate=float(original.get("exchange_rate") or 1),

            company_id=original.get("company_id"),

            lines=reversed_lines,

            idempotency_key=f"reversal:{journal_id}",

        )

        reversal_id = str(reversal_journal["journal"]["id"])



        approval_service.submit_for_approval(org_id, journal_id=reversal_id, actor_id=reversed_by)

        final_approver = approver_id or reversed_by

        approval_service.approve(

            org_id,

            journal_id=reversal_id,

            approver_id=str(final_approver or "system"),

            skip_maker_checker=approver_id is None,

        )

        post_result = posting_orchestrator.post_journal(org_id, journal_id=reversal_id, posted_by=reversed_by)



        journal_repository.set_status(org_id, journal_id=journal_id, journal_status="reversed")

        reversal_repository.create(

            org_id,

            original_journal_id=journal_id,

            reversal_journal_id=reversal_id,

            reversal_reason=reversal_reason,

            reversed_by=reversed_by,

        )

        emit_journal_reversed(org_id, journal_id, reversal_journal_id=reversal_id)

        metrics_store.incr_journal_reversal()

        try:

            from app.modules.erp.journals.services.journal_realtime_service import journal_realtime_service



            journal_realtime_service.push_reversed(org_id, journal_id=journal_id, reversal_journal_id=reversal_id)

        except Exception:

            pass

        try:

            from app.modules.platform.governance.services.audit_service import audit_service



            audit_service.record(

                org_id=org_id,

                actor_type="user",

                actor_id=reversed_by or "erp.journals",

                action="journal.reversed",

                object_ref=f"erp:journal:{journal_id}",

                payload={"reversal_journal_id": reversal_id, "reason": reversal_reason},

                entity_type="journal",

                entity_id=journal_id,

                source_service="erp.journals",

            )

        except Exception:

            pass

        return {

            "original_journal_id": journal_id,

            "reversal_journal_id": reversal_id,

            "post_result": post_result,

        }





journal_reversal_service = JournalReversalService()


