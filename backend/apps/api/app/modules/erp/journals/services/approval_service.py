from __future__ import annotations



from app.modules.core.iam.services.maker_checker_service import MakerCheckerViolation, enforce_maker_checker

from app.modules.erp.journals.events.journal_events import emit_journal_approved

from app.modules.erp.journals.repositories.journal_line_repository import journal_line_repository

from app.modules.erp.journals.repositories.journal_repository import journal_repository

from app.modules.erp.journals.services.journal_validation_service import journal_validation_service

from app.services.metrics import metrics_store





class ApprovalService:

    def submit_for_approval(self, org_id: str, *, journal_id: str, actor_id: str | None) -> dict:

        journal = journal_repository.get(org_id, journal_id=journal_id)

        if not journal:

            raise ValueError("Journal not found")

        if str(journal.get("journal_status")) != "draft":

            raise ValueError("Only draft journals can be submitted for approval")

        lines = journal_line_repository.list_by_journal(org_id, journal_id=journal_id)

        try:

            journal_validation_service.validate_submit(org_id, journal=journal, lines=lines)

        except ValueError:

            metrics_store.incr_journal_validation_failure()

            raise

        journal_repository.set_status(org_id, journal_id=journal_id, journal_status="pending_approval")

        metrics_store.incr_journal_submitted()

        return {"journal_id": journal_id, "journal_status": "pending_approval"}



    def approve(self, org_id: str, *, journal_id: str, approver_id: str, skip_maker_checker: bool = False) -> dict:

        journal = journal_repository.get(org_id, journal_id=journal_id)

        if not journal:

            raise ValueError("Journal not found")

        status = str(journal.get("journal_status"))

        if status not in {"draft", "pending_approval"}:

            raise ValueError(f"Cannot approve journal in status '{status}'")

        if not skip_maker_checker:

            try:

                enforce_maker_checker(

                    created_by=str(journal.get("created_by") or ""),

                    actor_user_id=approver_id,

                    org_id=org_id,

                )

            except MakerCheckerViolation as exc:

                raise ValueError(str(exc)) from exc



        lines = journal_line_repository.list_by_journal(org_id, journal_id=journal_id)

        try:

            journal_validation_service.validate_approve(org_id, journal=journal, lines=lines)

        except ValueError:

            metrics_store.incr_journal_validation_failure()

            raise



        journal_repository.set_status(

            org_id,

            journal_id=journal_id,

            journal_status="approved",

            approved_by=approver_id,

        )

        emit_journal_approved(org_id, journal_id, approved_by=approver_id)

        metrics_store.incr_journal_approved()

        try:

            from app.modules.erp.journals.services.journal_realtime_service import journal_realtime_service



            journal_realtime_service.push_approved(org_id, journal_id=journal_id, approved_by=approver_id)

        except Exception:

            pass

        try:

            from app.modules.platform.governance.services.audit_service import audit_service



            audit_service.record(

                org_id=org_id,

                actor_type="user",

                actor_id=approver_id,

                action="journal.approved",

                object_ref=f"erp:journal:{journal_id}",

                payload={"journal_number": journal.get("journal_number")},

                entity_type="journal",

                entity_id=journal_id,

                source_service="erp.journals",

            )

        except Exception:

            pass

        return {"journal_id": journal_id, "journal_status": "approved", "approved_by": approver_id}



    def reject(self, org_id: str, *, journal_id: str, actor_id: str) -> dict:

        journal = journal_repository.get(org_id, journal_id=journal_id)

        if not journal:

            raise ValueError("Journal not found")

        if str(journal.get("journal_status")) != "pending_approval":

            raise ValueError("Only pending_approval journals can be rejected")

        journal_repository.set_status(org_id, journal_id=journal_id, journal_status="draft")

        return {"journal_id": journal_id, "journal_status": "draft", "rejected_by": actor_id}



    def list_approval_queue(self, org_id: str, *, limit: int = 100, offset: int = 0) -> list[dict]:

        return journal_repository.list(

            org_id,

            journal_status="pending_approval",

            limit=limit,

            offset=offset,

        )





approval_service = ApprovalService()


