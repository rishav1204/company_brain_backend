from __future__ import annotations

from app.services.db import get_db_conn, set_rls_org


class LedgerQueryRepository:
    def list_entries(
        self,
        org_id: str,
        *,
        account_id: str | None = None,
        batch_id: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        branch_ids: list[str] | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict]:
        limit = max(1, min(int(limit or 200), 500))
        offset = max(0, int(offset or 0))
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if account_id:
            where.append("account_id = %s::uuid")
            params.append(account_id)
        if batch_id:
            where.append("batch_id = %s::uuid")
            params.append(batch_id)
        if reference_type:
            where.append("reference_type = %s")
            params.append(reference_type)
        if reference_id:
            where.append("reference_id = %s::uuid")
            params.append(reference_id)
        if branch_ids:
            where.append("(branch_id IS NULL OR branch_id::text = ANY(%s))")
            params.append([str(b) for b in branch_ids])
        sql = f"""
            SELECT id::text, batch_id::text, account_id::text, entry_type,
                   debit_amount, credit_amount, currency_code, exchange_rate,
                   posting_date::text, fiscal_period_id::text,
                   reference_type, reference_id::text, cost_center_id::text,
                   branch_id::text, created_at::text
            FROM erp.ledger_entries
            WHERE {' AND '.join(where)}
            ORDER BY posting_date DESC, created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                return [dict(r) for r in (cur.fetchall() or [])]

    def get_batch_entries(self, org_id: str, *, batch_id: str, limit: int = 500) -> list[dict]:
        limit = max(1, min(int(limit or 500), 2000))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, account_id::text, debit_amount, credit_amount,
                           currency_code, exchange_rate, posting_date::text, fiscal_period_id::text,
                           entry_type, journal_id::text, reference_type, reference_id::text, cost_center_id::text
                    FROM erp.ledger_entries
                    WHERE org_id = %s::uuid AND batch_id = %s::uuid
                    ORDER BY created_at ASC
                    LIMIT %s
                    """,
                    (org_id, batch_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


ledger_query_repository = LedgerQueryRepository()

