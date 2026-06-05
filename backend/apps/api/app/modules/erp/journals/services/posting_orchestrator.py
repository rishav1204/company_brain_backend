from __future__ import annotations



import time



from app.modules.erp.gl.services.posting_service import posting_service

from app.modules.erp.journals.events.journal_events import emit_journal_posted

from app.modules.erp.journals.events.posting_events import emit_posting_completed

from app.modules.erp.journals.repositories.journal_line_repository import journal_line_repository

from app.modules.erp.journals.repositories.journal_repository import journal_repository

from app.modules.erp.journals.services.journal_validation_service import journal_validation_service

from app.services.db import get_db_conn, set_rls_org

from app.services.metrics import metrics_store





class PostingOrchestrator:

    def post_journal(self, org_id: str, *, journal_id: str, posted_by: str | None) -> dict:

        started = time.time()

        journal = journal_repository.get(org_id, journal_id=journal_id)

        if not journal:

            raise ValueError("Journal not found")



        if str(journal.get("journal_status")) == "posted" and journal.get("ledger_batch_id"):

            return {

                "journal_id": journal_id,

                "journal_status": "posted",

                "ledger_batch_id": journal.get("ledger_batch_id"),

                "idempotent": True,

            }



        lines = journal_line_repository.list_by_journal(org_id, journal_id=journal_id)

        journal_validation_service.validate_post(org_id, journal=journal, lines=lines)



        gl_lines = [

            {

                "account_id": line["account_id"],

                "debit_amount": float(line.get("debit_amount") or 0),

                "credit_amount": float(line.get("credit_amount") or 0),

                "currency_code": journal.get("currency_code") or "INR",

                "exchange_rate": float(journal.get("exchange_rate") or 1),

                "entry_type": str(journal.get("journal_type") or "journal"),

                "journal_id": journal_id,

                "reference_type": journal.get("source_type"),

                "reference_id": journal.get("source_id"),

                "cost_center_id": line.get("cost_center_id"),

            }

            for line in lines

        ]



        try:

            with get_db_conn() as conn:

                set_rls_org(conn, org_id)

                locked = journal_repository.get_conn(conn, org_id, journal_id=journal_id)

                if not locked:

                    raise ValueError("Journal not found")

                if str(locked.get("journal_status")) == "posted" and locked.get("ledger_batch_id"):

                    return {

                        "journal_id": journal_id,

                        "journal_status": "posted",

                        "ledger_batch_id": locked.get("ledger_batch_id"),

                        "idempotent": True,

                    }



                gl_result = posting_service.post_with_conn(

                    conn,

                    org_id,

                    posted_by=posted_by,

                    posting_date=str(journal.get("posting_date")),

                    lines=gl_lines,

                    company_id=journal.get("company_id"),

                )

                batch_id = str(gl_result.get("batch_id") or "")

                journal_repository.set_status_conn(

                    conn,

                    org_id,

                    journal_id=journal_id,

                    journal_status="posted",

                    posted_by=posted_by,

                    ledger_batch_id=batch_id or None,

                )

        except ValueError:

            metrics_store.incr_journal_validation_failure()

            raise

        except Exception:

            metrics_store.incr_journal_posting_failure()

            raise



        latency_ms = int((time.time() - started) * 1000)

        metrics_store.incr_journal_posting()

        metrics_store.observe_journal_posting_latency_ms(latency_ms)



        emit_journal_posted(org_id, journal_id, batch_id=batch_id, posted_by=posted_by)

        emit_posting_completed(org_id, journal_id, batch_id=batch_id, latency_ms=latency_ms)

        try:

            from app.modules.erp.journals.services.journal_realtime_service import journal_realtime_service



            journal_realtime_service.push_posted(org_id, journal_id=journal_id, batch_id=batch_id)

        except Exception:

            pass

        try:

            from app.modules.platform.governance.services.audit_service import audit_service



            audit_service.record(

                org_id=org_id,

                actor_type="user",

                actor_id=posted_by or "erp.journals",

                action="journal.posted",

                object_ref=f"erp:journal:{journal_id}",

                payload={"ledger_batch_id": batch_id, "journal_number": journal.get("journal_number")},

                entity_type="journal",

                entity_id=journal_id,

                source_service="erp.journals",

            )

        except Exception:

            pass

        return {

            "journal_id": journal_id,

            "journal_status": "posted",

            "ledger_batch_id": batch_id,

            "gl_result": gl_result,

        }



    def post_batch(self, org_id: str, *, journal_ids: list[str], posted_by: str | None) -> list[dict]:

        results: list[dict] = []

        for jid in journal_ids:

            try:

                results.append(self.post_journal(org_id, journal_id=jid, posted_by=posted_by))

            except Exception as exc:

                results.append({"journal_id": jid, "error": str(exc), "journal_status": "failed"})

        return results





posting_orchestrator = PostingOrchestrator()


