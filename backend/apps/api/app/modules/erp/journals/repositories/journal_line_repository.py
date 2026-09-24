from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class JournalLineRepository:
    def replace_lines_conn(self, conn, org_id: str, *, journal_id: str, lines: list[dict]) -> list[dict]:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM erp.journal_lines
                WHERE org_id = %s::uuid AND journal_id = %s::uuid
                """,
                (org_id, journal_id),
            )
            out: list[dict] = []
            if lines:
                params = [
                    (
                        str(uuid4()),
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
                    )
                    for line in lines
                ]
                cur.executemany(
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
                    """,
                    params,
                )
            return out

    def list_by_journal_conn(self, conn, org_id: str, *, journal_id: str, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, account_id::text, line_description,
                       debit_amount, credit_amount, cost_center_id::text,
                       tax_code, reference_type, reference_id::text, created_at::text
                FROM erp.journal_lines
                WHERE org_id = %s::uuid AND journal_id = %s::uuid
                ORDER BY created_at ASC
                    LIMIT %s
                """,
                (org_id, journal_id, limit),
            )
            return [dict(r) for r in (cur.fetchall() or [])]

    def replace_lines(self, org_id: str, *, journal_id: str, lines: list[dict]) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            return self.replace_lines_conn(conn, org_id, journal_id=journal_id, lines=lines)

    def list_by_journal(self, org_id: str, *, journal_id: str, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit)
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
                    LIMIT %s
                    """,
                    (org_id, journal_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


journal_line_repository = JournalLineRepository()
