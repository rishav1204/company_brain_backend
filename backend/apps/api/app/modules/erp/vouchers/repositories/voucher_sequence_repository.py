from __future__ import annotations

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class VoucherSequenceRepository:
    def next_sequence(
        self,
        org_id: str,
        *,
        voucher_type: str,
        financial_year: str,
        company_id: str | None = None,
    ) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, current_sequence
                    FROM erp.voucher_sequences
                    WHERE org_id = %s::uuid
                      AND voucher_type = %s
                      AND financial_year = %s
                      AND company_id IS NOT DISTINCT FROM %s::uuid
                    FOR UPDATE
                    """,
                    (org_id, voucher_type, financial_year, company_id),
                )
                row = cur.fetchone()
                if row:
                    seq = int(row["current_sequence"]) + 1
                    cur.execute(
                        """
                        UPDATE erp.voucher_sequences
                        SET current_sequence = %s, updated_at = now()
                        WHERE id = %s::uuid
                        """,
                        (seq, row["id"]),
                    )
                    return seq
                sid = str(uuid4())
                cur.execute(
                    """
                    INSERT INTO erp.voucher_sequences (
                      id, org_id, company_id, voucher_type, financial_year, current_sequence
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, 1)
                    """,
                    (sid, org_id, company_id, voucher_type, financial_year),
                )
                return 1


voucher_sequence_repository = VoucherSequenceRepository()
