from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class AdjustmentRepository:
    def create(
        self,
        org_id: str,
        *,
        bank_transaction_id: str | None,
        reconciliation_id: str | None,
        adjustment_type: str,
        amount: float,
        expense_account_id: str | None,
        bank_account_id: str | None,
        metadata: dict | None = None,
    ) -> dict:
        aid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.reconciliation_adjustments (
                      id, org_id, bank_transaction_id, reconciliation_id,
                      adjustment_type, amount, expense_account_id, bank_account_id,
                      status, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s,%s,%s::uuid,%s::uuid,'draft',%s::jsonb)
                    RETURNING id::text, adjustment_type, amount, status
                    """,
                    (
                        aid, org_id, bank_transaction_id, reconciliation_id,
                        adjustment_type, amount, expense_account_id, bank_account_id,
                        Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": aid})

    def get(self, org_id: str, *, adjustment_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, bank_transaction_id::text, reconciliation_id::text,
                           adjustment_type, amount, expense_account_id::text, bank_account_id::text,
                           status, journal_id::text, metadata
                    FROM erp.reconciliation_adjustments
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, adjustment_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def mark_posted(self, org_id: str, *, adjustment_id: str, journal_id: str, approved_by: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.reconciliation_adjustments
                    SET status = 'posted', journal_id = %s::uuid, approved_by = %s::uuid,
                        approved_at = NOW(), updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, status, journal_id::text
                    """,
                    (journal_id, approved_by, org_id, adjustment_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Adjustment not found")
                return dict(row)


adjustment_repository = AdjustmentRepository()
