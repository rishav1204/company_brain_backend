from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class VoucherLineRepository:
    def replace_lines(self, org_id: str, *, voucher_id: str, lines: list[dict]) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM erp.voucher_lines WHERE org_id = %s::uuid AND voucher_id = %s::uuid",
                    (org_id, voucher_id),
                )
                out: list[dict] = []
                for idx, line in enumerate(lines, start=1):
                    lid = str(uuid4())
                    cur.execute(
                        """
                        INSERT INTO erp.voucher_lines (
                          id, org_id, voucher_id, line_number, account_id,
                          debit_amount, credit_amount, narration, cost_center_id, tax_code,
                          party_type, party_id, reference_type, reference_id
                        )
                        VALUES (
                          %s::uuid, %s::uuid, %s::uuid, %s, %s::uuid,
                          %s::numeric, %s::numeric, %s, %s::uuid, %s,
                          %s, %s::uuid, %s, %s::uuid
                        )
                        RETURNING id::text, line_number, account_id::text,
                                  debit_amount::float8, credit_amount::float8, narration
                        """,
                        (
                            lid, org_id, voucher_id, idx, line["account_id"],
                            line.get("debit_amount") or 0, line.get("credit_amount") or 0,
                            line.get("narration") or line.get("line_description"),
                            line.get("cost_center_id"), line.get("tax_code"),
                            line.get("party_type"), line.get("party_id"),
                            line.get("reference_type"), line.get("reference_id"),
                        ),
                    )
                    out.append(dict(cur.fetchone() or {}))
                return out

    def list_by_voucher(self, org_id: str, *, voucher_id: str, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, line_number, account_id::text,
                           debit_amount::float8, credit_amount::float8, narration,
                           cost_center_id::text, tax_code, party_type, party_id::text,
                           reference_type, reference_id::text
                    FROM erp.voucher_lines
                    WHERE org_id = %s::uuid AND voucher_id = %s::uuid
                    ORDER BY line_number
                    LIMIT %s
                    """,
                    (org_id, voucher_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]


voucher_line_repository = VoucherLineRepository()
