from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class CustomerBalanceRepository:
    def upsert(
        self,
        org_id: str,
        *,
        customer_id: str,
        outstanding_amount: float,
        credit_used: float | None = None,
    ) -> dict:
        bid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.customer_balances (id, org_id, customer_id, outstanding_amount, credit_used, last_updated)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::numeric, %s::numeric, NOW())
                    ON CONFLICT (org_id, customer_id)
                    DO UPDATE SET
                      outstanding_amount = EXCLUDED.outstanding_amount,
                      credit_used = COALESCE(EXCLUDED.credit_used, erp.customer_balances.credit_used),
                      last_updated = NOW()
                    RETURNING customer_id::text, outstanding_amount, credit_used, last_updated::text
                    """,
                    (bid, org_id, customer_id, outstanding_amount, credit_used or outstanding_amount),
                )
                return dict(cur.fetchone() or {"customer_id": customer_id})

    def get(self, org_id: str, *, customer_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT customer_id::text, outstanding_amount, credit_used, last_updated::text
                    FROM erp.customer_balances
                    WHERE org_id = %s::uuid AND customer_id = %s::uuid
                    """,
                    (org_id, customer_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(self, org_id: str, limit: int = 500) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT cb.customer_id::text, c.customer_name, cb.outstanding_amount, cb.credit_used, cb.last_updated::text
                    FROM erp.customer_balances cb
                    JOIN erp.customers c ON c.id = cb.customer_id AND c.org_id = cb.org_id
                    WHERE cb.org_id = %s::uuid
                    ORDER BY cb.outstanding_amount DESC
                    LIMIT %s
                    """,
                    (org_id,),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def compute_gl_outstanding(
        self,
        org_id: str,
        *,
        customer_id: str,
        receivable_account_id: str,
    ) -> float:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(le.debit_amount - le.credit_amount), 0) AS balance
                    FROM erp.ledger_entries le
                    JOIN erp.journals j ON j.id = le.journal_id AND j.org_id = le.org_id
                    WHERE le.org_id = %s::uuid
                      AND le.account_id = %s::uuid
                      AND j.journal_status = 'posted'
                      AND (
                        (j.source_type = 'ar_invoice' AND j.source_id IN (
                          SELECT id FROM erp.ar_invoices WHERE org_id = %s::uuid AND customer_id = %s::uuid
                        ))
                        OR
                        (j.source_type = 'ar_receipt' AND j.source_id IN (
                          SELECT id FROM erp.customer_receipts WHERE org_id = %s::uuid AND customer_id = %s::uuid
                        ))
                        OR
                        (j.source_type = 'ar_writeoff' AND j.source_id IN (
                          SELECT id FROM erp.ar_invoices WHERE org_id = %s::uuid AND customer_id = %s::uuid
                        ))
                      )
                    """,
                    (
                        org_id, receivable_account_id,
                        org_id, customer_id, org_id, customer_id, org_id, customer_id,
                    ),
                )
                row = cur.fetchone()
                return float((row or {}).get("balance") or 0)


customer_balance_repository = CustomerBalanceRepository()
