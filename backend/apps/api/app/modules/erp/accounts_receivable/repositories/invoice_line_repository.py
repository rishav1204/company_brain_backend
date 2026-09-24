from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class ArInvoiceLineRepository:
    def replace_lines(self, org_id: str, *, invoice_id: str, lines: list[dict]) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM erp.ar_invoice_lines WHERE org_id = %s::uuid AND invoice_id = %s::uuid",
                    (org_id, invoice_id),
                )
                for line in lines:
                    cur.execute(
                        """
                        INSERT INTO erp.ar_invoice_lines (
                          id, org_id, invoice_id, line_type, account_id, description,
                          amount, tax_code, cost_center_id
                        )
                        VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s::uuid,%s,%s::numeric,%s,%s::uuid)
                        """,
                        (
                            str(uuid4()), org_id, invoice_id,
                            line.get("line_type", "revenue"),
                            line.get("account_id"),
                            line.get("description"),
                            line.get("amount", 0),
                            line.get("tax_code"),
                            line.get("cost_center_id"),
                        ),
                    )

    def list_by_invoice(self, org_id: str, *, invoice_id: str, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, line_type, account_id::text, description, amount, tax_code, cost_center_id::text
                    FROM erp.ar_invoice_lines
                    WHERE org_id = %s::uuid AND invoice_id = %s::uuid
                    ORDER BY created_at ASC
                    LIMIT %s
                    """,
                    (org_id, invoice_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


ar_invoice_line_repository = ArInvoiceLineRepository()
