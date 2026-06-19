from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class CardExpenseService:
    def list_unallocated(self, org_id: str, *, employee_id: str | None = None, limit: int = 100) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if employee_id:
                    cur.execute(
                        """
                        SELECT id::text, employee_id::text, transaction_date::text, amount, merchant_name, allocation_status
                        FROM erp.corporate_card_transactions
                        WHERE org_id = %s::uuid AND employee_id = %s::uuid AND allocation_status = 'unallocated'
                        ORDER BY transaction_date DESC LIMIT %s
                        """,
                        (org_id, employee_id, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, employee_id::text, transaction_date::text, amount, merchant_name, allocation_status
                        FROM erp.corporate_card_transactions
                        WHERE org_id = %s::uuid AND allocation_status = 'unallocated'
                        ORDER BY transaction_date DESC LIMIT %s
                        """,
                        (org_id, limit),
                    )
                return [dict(r) for r in cur.fetchall()]

    def import_from_bank_feed(
        self,
        org_id: str,
        *,
        employee_id: str | None,
        transaction_date: str,
        amount: float,
        merchant_name: str | None = None,
        card_last4: str | None = None,
        bank_feed_ref: str | None = None,
    ) -> dict:
        tid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.corporate_card_transactions (
                      id, org_id, employee_id, card_last4, transaction_date, amount,
                      merchant_name, bank_feed_ref, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s::date,%s::numeric,%s,%s,%s::jsonb)
                    RETURNING id::text, allocation_status
                    """,
                    (tid, org_id, employee_id, card_last4, transaction_date, amount, merchant_name, bank_feed_ref, Json({})),
                )
                return dict(cur.fetchone() or {"id": tid})

    def allocate(self, org_id: str, *, transaction_id: str, claim_item_id: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.corporate_card_transactions
                    SET allocation_status = 'allocated', claim_item_id = %s::uuid
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, allocation_status, claim_item_id::text
                    """,
                    (claim_item_id, org_id, transaction_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {}


card_expense_service = CardExpenseService()
