from __future__ import annotations

import uuid

from app.modules.erp.gl.repositories.ledger_query_repository import ledger_query_repository
from app.modules.erp.gl.repositories.ledger_repository import ledger_repository
from app.services.db import get_db_conn, set_rls_org


class ReversalService:
    def reverse_batch(self, org_id: str, *, batch_id: str, reversed_by: str | None) -> dict:
        entries = ledger_query_repository.get_batch_entries(org_id, batch_id=batch_id)
        if not entries:
            raise ValueError("Batch not found or has no entries")

        posting_date = str(entries[0]["posting_date"])
        fiscal_period_id = str(entries[0]["fiscal_period_id"])

        lines: list[dict] = []
        for e in entries:
            # Reverse by swapping sides; keep references
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
            batch = ledger_repository.create_batch(conn, org_id, batch_number=batch_number, posted_by=reversed_by)
            new_batch_id = str(batch["id"])
            ledger_repository.insert_entries(
                conn,
                org_id,
                batch_id=new_batch_id,
                fiscal_period_id=fiscal_period_id,
                posting_date=posting_date,
                lines=lines,
            )

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

        return {"reversed_batch_id": batch_id, "reversal_batch_id": new_batch_id, "batch": batch}


reversal_service = ReversalService()

