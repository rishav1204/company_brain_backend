from __future__ import annotations

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class ReversalRepository:
    def create(
        self,
        org_id: str,
        *,
        original_journal_id: str,
        reversal_journal_id: str,
        reversal_reason: str | None,
        reversed_by: str | None,
    ) -> dict:
        rid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.journal_reversals (
                      id, org_id, original_journal_id, reversal_journal_id,
                      reversal_reason, reversed_by
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s::uuid)
                    RETURNING id::text, original_journal_id::text, reversal_journal_id::text,
                              reversal_reason, reversed_by::text, reversed_at::text
                    """,
                    (rid, org_id, original_journal_id, reversal_journal_id, reversal_reason, reversed_by),
                )
                return dict(cur.fetchone() or {"id": rid})

    def get_by_original(self, org_id: str, *, original_journal_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, original_journal_id::text, reversal_journal_id::text,
                           reversal_reason, reversed_by::text, reversed_at::text
                    FROM erp.journal_reversals
                    WHERE org_id = %s::uuid AND original_journal_id = %s::uuid
                    LIMIT 1
                    """,
                    (org_id, original_journal_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None


reversal_repository = ReversalRepository()
