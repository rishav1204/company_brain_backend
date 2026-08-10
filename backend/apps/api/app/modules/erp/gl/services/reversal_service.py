from __future__ import annotations

import uuid

from app.modules.erp.gl.repositories.ledger_query_repository import ledger_query_repository
from app.modules.erp.gl.services.posting_service import POSTING_INTERNAL, posting_service
from app.services.db import get_db_conn, set_rls_org


class ReversalService:
    def reverse_batch_with_conn(
        self,
        conn,
        org_id: str,
        *,
        batch_id: str,
        reversed_by: str | None,
        batch_number: str | None = None,
    ) -> dict:
        entries = ledger_query_repository.get_batch_entries(org_id, batch_id=batch_id)
        if not entries:
            raise ValueError("Batch not found or has no entries")

        posting_date = str(entries[0]["posting_date"])
        company_id = entries[0].get("company_id")

        lines: list[dict] = []
        for e in entries:
            lines.append(
                {
                    "account_id": e["account_id"],
                    "debit_amount": float(e.get("credit_amount") or 0),
                    "credit_amount": float(e.get("debit_amount") or 0),
                    "currency_code": e.get("currency_code") or "INR",
                    "exchange_rate": float(e.get("exchange_rate") or 1),
                    "entry_type": "reversal",
                    "journal_id": e.get("journal_id"),
                    "reference_type": "ledger_batch",
                    "reference_id": batch_id,
                    "cost_center_id": e.get("cost_center_id"),
                }
            )

        batch_number = batch_number or ("RB-" + uuid.uuid4().hex[:12].upper())
        set_rls_org(conn, org_id)
        return posting_service.post_with_conn(
            conn,
            org_id,
            posted_by=reversed_by,
            posting_date=posting_date,
            lines=lines,
            company_id=str(company_id) if company_id else None,
            batch_number=batch_number,
            _posting_caller=POSTING_INTERNAL,
        )

    def reverse_batch(self, org_id: str, *, batch_id: str, reversed_by: str | None) -> dict:
        entries = ledger_query_repository.get_batch_entries(org_id, batch_id=batch_id)
        if not entries:
            raise ValueError("Batch not found or has no entries")

        posting_date = str(entries[0]["posting_date"])
        company_id = entries[0].get("company_id")

        lines: list[dict] = []
        for e in entries:
            lines.append(
                {
                    "account_id": e["account_id"],
                    "debit_amount": float(e.get("credit_amount") or 0),
                    "credit_amount": float(e.get("debit_amount") or 0),
                    "currency_code": e.get("currency_code") or "INR",
                    "exchange_rate": float(e.get("exchange_rate") or 1),
                    "entry_type": "reversal",
                    "journal_id": e.get("journal_id"),
                    "reference_type": "ledger_batch",
                    "reference_id": batch_id,
                    "cost_center_id": e.get("cost_center_id"),
                }
            )

        batch_number = "RB-" + uuid.uuid4().hex[:12].upper()
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            gl_result = self.reverse_batch_with_conn(
                conn, org_id, batch_id=batch_id, reversed_by=reversed_by, batch_number=batch_number
            )
            new_batch_id = str(gl_result.get("batch_id") or "")

        try:
            from app.modules.platform.events.services.event_service import platform_event_service

            platform_event_service.publish(
                event_type="erp.ledger.reversed",
                org_id=org_id,
                source="erp.gl",
                entity_type="ledger_batch",
                entity_id=new_batch_id,
                payload={"reversed_batch_id": batch_id, "reversal_batch_id": new_batch_id},
            )
        except Exception:
            pass

        return {
            "reversed_batch_id": batch_id,
            "reversal_batch_id": new_batch_id,
            "batch": gl_result.get("batch"),
            "gl_result": gl_result,
        }


reversal_service = ReversalService()
