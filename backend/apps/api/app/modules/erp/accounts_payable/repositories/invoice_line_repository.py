from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class InvoiceLineRepository:
    def replace_lines(self, org_id: str, *, invoice_id: str, lines: list[dict]) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM erp.ap_invoice_lines WHERE org_id = %s::uuid AND invoice_id = %s::uuid",
                    (org_id, invoice_id),
                )
                out: list[dict] = []
                for line in lines:
                    lid = str(uuid4())
                    cur.execute(
                        """
                        INSERT INTO erp.ap_invoice_lines (
                          id, org_id, invoice_id, account_id, line_type, description,
                          amount, tax_code, cost_center_id
                        )
                        VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s,%s,%s::numeric,%s,%s::uuid)
                        RETURNING id::text, account_id::text, line_type, description, amount, tax_code
                        """,
                        (
                            lid, org_id, invoice_id,
                            line.get("account_id"), line.get("line_type", "expense"),
                            line.get("description"), float(line.get("amount") or 0),
                            line.get("tax_code"), line.get("cost_center_id"),
                        ),
                    )
                    row = cur.fetchone()
                    if row:
                        out.append(dict(row))
                return out

    def list_by_invoice(self, org_id: str, *, invoice_id: str, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit, default=500, maximum=500)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, account_id::text, line_type, description, amount, tax_code,
                           cost_center_id::text
                    FROM erp.ap_invoice_lines
                    WHERE org_id = %s::uuid AND invoice_id = %s::uuid
                    ORDER BY created_at ASC
                    LIMIT %s
                    """,
                    (org_id, invoice_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


invoice_line_repository = InvoiceLineRepository()
