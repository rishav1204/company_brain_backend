from __future__ import annotations

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class JournalLineRepository:
    def replace_lines(self, org_id: str, *, journal_id: str, lines: list[dict]) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM erp.journal_lines
                    WHERE org_id = %s::uuid AND journal_id = %s::uuid
                    """,
                    (org_id, journal_id),
                )
                out: list[dict] = []
                for line in lines:
                    lid = str(uuid4())
                    cur.execute(
                        """
                        INSERT INTO erp.journal_lines (
                          id, org_id, journal_id, account_id, line_description,
                          debit_amount, credit_amount, cost_center_id, tax_code,
                          reference_type, reference_id
                        )
                        VALUES (
                          %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s,
                          %s::numeric, %s::numeric, %s::uuid, %s, %s, %s::uuid
                        )
                        RETURNING id::text, account_id::text, line_description,
                                  debit_amount, credit_amount, cost_center_id::text,
                                  tax_code, reference_type, reference_id::text
                        """,
                        (
                            lid,
                            org_id,
                            journal_id,
                            line["account_id"],
                            line.get("line_description"),
                            float(line.get("debit_amount") or 0),
                            float(line.get("credit_amount") or 0),
                            line.get("cost_center_id"),
                            line.get("tax_code"),
                            line.get("reference_type"),
                            line.get("reference_id"),
                        ),
                    )
                    row = cur.fetchone()
                    if row:
                        out.append(dict(row))
                return out

    def list_by_journal(self, org_id: str, *, journal_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, account_id::text, line_description,
                           debit_amount, credit_amount, cost_center_id::text,
                           tax_code, reference_type, reference_id::text, created_at::text
                    FROM erp.journal_lines
                    WHERE org_id = %s::uuid AND journal_id = %s::uuid
                    ORDER BY created_at ASC
                    """,
                    (org_id, journal_id),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


journal_line_repository = JournalLineRepository()
