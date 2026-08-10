from __future__ import annotations

import time

from app.modules.erp.gl.services.posting_service import POSTING_INTERNAL, posting_service
from app.modules.erp.journals.events.journal_events import emit_journal_posted
from app.modules.erp.journals.events.posting_events import emit_posting_completed
from app.modules.erp.journals.repositories.journal_line_repository import journal_line_repository
from app.modules.erp.journals.repositories.journal_repository import journal_repository
from app.modules.erp.journals.services.journal_validation_service import journal_validation_service
from app.services.db import get_db_conn, set_rls_org
from app.services.metrics import metrics_store


class PostingOrchestrator:
    def post_journal_with_conn(
        self,
        conn,
        org_id: str,
        *,
        journal_id: str,
        posted_by: str | None,
        defer_side_effects: bool = False,
    ) -> dict:
        """Post journal using caller's connection. Side effects skipped when defer_side_effects=True."""
        journal = journal_repository.get_conn(conn, org_id, journal_id=journal_id)
        if not journal:
            raise ValueError("Journal not found")
        if str(journal.get("journal_status")) == "posted" and journal.get("ledger_batch_id"):
            return {
                "journal_id": journal_id,
                "journal_status": "posted",
                "ledger_batch_id": journal.get("ledger_batch_id"),
                "idempotent": True,
            }
        lines = journal_line_repository.list_by_journal_conn(conn, org_id, journal_id=journal_id)
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
        gl_result = posting_service.post_with_conn(
            conn,
            org_id,
            posted_by=posted_by,
            posting_date=str(journal.get("posting_date")),
            lines=gl_lines,
            company_id=journal.get("company_id"),
            _posting_caller=POSTING_INTERNAL,
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
        # INT-06: Record GST transactions atomically with journal posting for invoice sources.
        from app.modules.erp.tax.services.gst_transaction_service import gst_transaction_service

        source_type = str(journal.get("source_type") or "")
        source_id = str(journal.get("source_id") or "")
        if source_type in {"ap_invoice", "ar_invoice"} and source_id:
            gst_transaction_service.record_from_source_with_conn(
                conn, org_id, source_type=source_type, source_id=source_id
            )
        result = {
            "journal_id": journal_id,
            "journal_status": "posted",
            "ledger_batch_id": batch_id,
            "gl_result": gl_result,
        }
        if not defer_side_effects:
            self._emit_post_side_effects(org_id, journal_id=journal_id, journal=journal, batch_id=batch_id, posted_by=posted_by)
        return result

    def _emit_post_side_effects(
        self,
        org_id: str,
        *,
        journal_id: str,
        journal: dict,
        batch_id: str,
        posted_by: str | None,
        latency_ms: int = 0,
    ) -> None:
        metrics_store.incr_journal_posting()
        if latency_ms:
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
        try:
            from app.modules.erp.coa.repositories.account_usage_repository import account_usage_repository
            from app.modules.erp.journals.repositories.journal_line_repository import journal_line_repository

            for line in journal_line_repository.list_by_journal(org_id, journal_id=journal_id):
                account_usage_repository.upsert(
                    org_id,
                    account_id=str(line.get("account_id")),
                    has_balance=True,
                    used_in_journals=True,
                )
        except Exception as exc:
            from app.services.logger import log_event

            log_event(
                "erp.coa.account_usage_upsert_failed",
                org_id=org_id,
                journal_id=journal_id,
                error=str(exc),
            )

    def post_journal(self, org_id: str, *, journal_id: str, posted_by: str | None) -> dict:
        # RQ-11: Serialize posting per journal_id to prevent duplicate batches under concurrency/retry.
        from app.core.redis_lock import redis_lock

        with redis_lock(f"erp:journal:post:{org_id}:{journal_id}", ttl_seconds=90, wait_seconds=10.0):
            return self._post_journal_locked(org_id, journal_id=journal_id, posted_by=posted_by)

    def _post_journal_locked(self, org_id: str, *, journal_id: str, posted_by: str | None) -> dict:
        started = time.time()
        journal = journal_repository.get(org_id, journal_id=journal_id)
        if not journal:
            raise ValueError("Journal not found")
        from app.core.config import settings
        from app.modules.erp.security.company_scope import require_company_id_for_erp_write

        if settings.erp_require_company_id:
            require_company_id_for_erp_write(
                org_id=org_id,
                company_id=journal.get("company_id"),
                operation="post_journal",
            )
        if str(journal.get("journal_status")) == "posted" and journal.get("ledger_batch_id"):
            return {
                "journal_id": journal_id,
                "journal_status": "posted",
                "ledger_batch_id": journal.get("ledger_batch_id"),
                "idempotent": True,
            }
        lines = journal_line_repository.list_by_journal(org_id, journal_id=journal_id)
        journal_validation_service.validate_post(org_id, journal=journal, lines=lines)
        try:
            with get_db_conn() as conn:
                set_rls_org(conn, org_id)
                result = self.post_journal_with_conn(
                    conn, org_id, journal_id=journal_id, posted_by=posted_by, defer_side_effects=True
                )
        except ValueError:
            metrics_store.incr_journal_validation_failure()
            raise
        except Exception:
            metrics_store.incr_journal_posting_failure()
            raise
        latency_ms = int((time.time() - started) * 1000)
        self._emit_post_side_effects(
            org_id,
            journal_id=journal_id,
            journal=journal,
            batch_id=str(result.get("ledger_batch_id") or ""),
            posted_by=posted_by,
            latency_ms=latency_ms,
        )
        return result

    def post_batch(self, org_id: str, *, journal_ids: list[str], posted_by: str | None) -> list[dict]:
        results: list[dict] = []
        for jid in journal_ids:
            try:
                results.append(self.post_journal(org_id, journal_id=jid, posted_by=posted_by))
            except Exception as exc:
                results.append({"journal_id": jid, "error": str(exc), "journal_status": "failed"})
        return results


posting_orchestrator = PostingOrchestrator()
