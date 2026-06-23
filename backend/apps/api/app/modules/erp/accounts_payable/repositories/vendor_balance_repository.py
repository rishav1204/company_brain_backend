from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class VendorBalanceRepository:
    def upsert(self, org_id: str, *, vendor_id: str, outstanding_amount: float) -> dict:
        bid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.vendor_balances (id, org_id, vendor_id, outstanding_amount, last_updated)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::numeric, NOW())
                    ON CONFLICT (org_id, vendor_id)
                    DO UPDATE SET outstanding_amount = EXCLUDED.outstanding_amount, last_updated = NOW()
                    RETURNING vendor_id::text, outstanding_amount, last_updated::text
                    """,
                    (bid, org_id, vendor_id, outstanding_amount),
                )
                return dict(cur.fetchone() or {"vendor_id": vendor_id})

    def get(self, org_id: str, *, vendor_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT vendor_id::text, outstanding_amount, last_updated::text
                    FROM erp.vendor_balances
                    WHERE org_id = %s::uuid AND vendor_id = %s::uuid
                    """,
                    (org_id, vendor_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(self, org_id: str, limit: int = 500) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT vb.vendor_id::text, v.vendor_name, vb.outstanding_amount, vb.last_updated::text
                    FROM erp.vendor_balances vb
                    JOIN erp.vendors v ON v.id = vb.vendor_id AND v.org_id = vb.org_id
                    WHERE vb.org_id = %s::uuid
                    ORDER BY vb.outstanding_amount DESC
                    LIMIT %s
                    """,
                    (org_id,),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


    def compute_gl_outstanding(
        self,
        org_id: str,
        *,
        vendor_id: str,
        payable_account_id: str,
    ) -> float:
        """Net payable liability from posted GL entries linked to vendor AP journals."""
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(le.credit_amount - le.debit_amount), 0) AS balance
                    FROM erp.ledger_entries le
                    JOIN erp.journals j ON j.id = le.journal_id AND j.org_id = le.org_id
                    WHERE le.org_id = %s::uuid
                      AND le.account_id = %s::uuid
                      AND j.journal_status = 'posted'
                      AND (
                        (j.source_type = 'ap_invoice' AND j.source_id IN (
                          SELECT id FROM erp.ap_invoices WHERE org_id = %s::uuid AND vendor_id = %s::uuid
                        ))
                        OR
                        (j.source_type = 'ap_payment' AND j.source_id IN (
                          SELECT id FROM erp.ap_payments WHERE org_id = %s::uuid AND vendor_id = %s::uuid
                        ))
                      )
                    """,
                    (org_id, payable_account_id, org_id, vendor_id, org_id, vendor_id),
                )
                row = cur.fetchone()
                return float((row or {}).get("balance") or 0)


vendor_balance_repository = VendorBalanceRepository()
