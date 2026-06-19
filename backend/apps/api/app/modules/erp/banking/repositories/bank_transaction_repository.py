from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class BankTransactionRepository:
    def create(
        self,
        org_id: str,
        *,
        bank_account_id: str,
        transaction_reference: str,
        transaction_date: str,
        amount: float,
        transaction_type: str,
        currency_code: str,
        description: str | None,
        source: str,
        counterparty_ref: str | None = None,
        import_idempotency_key: str | None = None,
        metadata: dict | None = None,
        value_date: str | None = None,
        status: str = "imported",
        source_type: str | None = None,
        source_id: str | None = None,
    ) -> dict:
        tid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.bank_transactions (
                      id, org_id, bank_account_id, transaction_reference, transaction_date,
                      amount, transaction_type, currency_code, description, source,
                      counterparty_ref, import_idempotency_key, metadata, value_date, status,
                      source_type, source_id
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s::date,%s::numeric,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::date,%s,%s,%s::uuid)
                    RETURNING id::text, transaction_reference, amount, transaction_type, reconciliation_status, status
                    """,
                    (
                        tid, org_id, bank_account_id, transaction_reference, transaction_date,
                        amount, transaction_type, currency_code, description, source,
                        counterparty_ref, import_idempotency_key, Json(metadata or {}),
                        value_date or transaction_date, status, source_type, source_id,
                    ),
                )
                return dict(cur.fetchone() or {"id": tid})

    def find_by_idempotency(self, org_id: str, *, import_idempotency_key: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, transaction_reference, amount, reconciliation_status
                    FROM erp.bank_transactions
                    WHERE org_id = %s::uuid AND import_idempotency_key = %s
                    LIMIT 1
                    """,
                    (org_id, import_idempotency_key),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def get(self, org_id: str, *, transaction_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, bank_account_id::text, transaction_reference, transaction_date::text,
                           amount, transaction_type, currency_code, description, source,
                           counterparty_ref, reconciliation_status, journal_id::text, metadata, created_at::text
                    FROM erp.bank_transactions
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, transaction_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(
        self,
        org_id: str,
        *,
        bank_account_id: str | None = None,
        reconciliation_status: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        limit = max(1, min(limit, 500))
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if bank_account_id:
            where.append("bank_account_id = %s::uuid")
            params.append(bank_account_id)
        if reconciliation_status:
            where.append("reconciliation_status = %s")
            params.append(reconciliation_status)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, bank_account_id::text, transaction_reference, transaction_date::text,
                           amount, transaction_type, description, source, reconciliation_status
                    FROM erp.bank_transactions
                    WHERE {' AND '.join(where)}
                    ORDER BY transaction_date DESC, created_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def set_reconciliation_status(self, org_id: str, *, transaction_id: str, status: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.bank_transactions
                    SET reconciliation_status = %s, updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, reconciliation_status
                    """,
                    (status, org_id, transaction_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Transaction not found")
                return dict(row)

    def sum_by_account(self, org_id: str, *, bank_account_id: str, reconciled_only: bool = False) -> dict:
        where = "org_id = %s::uuid AND bank_account_id = %s::uuid"
        params: list = [org_id, bank_account_id]
        if reconciled_only:
            where += " AND reconciliation_status = 'matched'"
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                      COALESCE(SUM(CASE WHEN transaction_type = 'credit' THEN amount ELSE 0 END), 0) AS credits,
                      COALESCE(SUM(CASE WHEN transaction_type = 'debit' THEN amount ELSE 0 END), 0) AS debits
                    FROM erp.bank_transactions
                    WHERE {where}
                    """,
                    tuple(params),
                )
                row = cur.fetchone()
                return dict(row) if row else {"credits": 0, "debits": 0}

    def sum_for_date(self, org_id: str, *, bank_account_id: str, position_date: str, reconciled_only: bool = True) -> dict:
        where = "org_id = %s::uuid AND bank_account_id = %s::uuid AND transaction_date = %s::date"
        params: list = [org_id, bank_account_id, position_date]
        if reconciled_only:
            where += " AND reconciliation_status = 'matched'"
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                      COALESCE(SUM(CASE WHEN transaction_type = 'credit' THEN amount ELSE 0 END), 0) AS credits,
                      COALESCE(SUM(CASE WHEN transaction_type = 'debit' THEN amount ELSE 0 END), 0) AS debits
                    FROM erp.bank_transactions
                    WHERE {where}
                    """,
                    tuple(params),
                )
                row = cur.fetchone()
                return dict(row) if row else {"credits": 0, "debits": 0}


bank_transaction_repository = BankTransactionRepository()
