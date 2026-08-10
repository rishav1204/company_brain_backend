from __future__ import annotations

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class ParallelLedgerRepository:
    def create_ledger(
        self,
        org_id: str,
        *,
        ledger_code: str,
        ledger_name: str,
        accounting_standard: str = "IFRS",
        company_id: str | None = None,
    ) -> dict:
        lid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.parallel_ledgers (
                      id, org_id, company_id, ledger_code, ledger_name, accounting_standard
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s)
                    ON CONFLICT (org_id, ledger_code) DO UPDATE
                      SET ledger_name = EXCLUDED.ledger_name,
                          accounting_standard = EXCLUDED.accounting_standard,
                          is_active = true
                    RETURNING id::text, ledger_code, ledger_name, accounting_standard,
                              is_active, company_id::text, created_at::text
                    """,
                    (lid, org_id, company_id, ledger_code, ledger_name, accounting_standard),
                )
                return dict(cur.fetchone() or {"id": lid})

    def get_ledger(self, org_id: str, *, ledger_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, ledger_code, ledger_name, accounting_standard,
                           is_active, company_id::text, created_at::text
                    FROM erp.parallel_ledgers
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, ledger_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list_ledgers(self, org_id: str, *, active_only: bool = True, limit: int = 50) -> list[dict]:
        limit = max(1, min(int(limit or 50), 200))
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if active_only:
            where.append("is_active = true")
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, ledger_code, ledger_name, accounting_standard,
                           is_active, company_id::text, created_at::text
                    FROM erp.parallel_ledgers
                    WHERE {' AND '.join(where)}
                    ORDER BY ledger_code ASC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def insert_entry(
        self,
        org_id: str,
        *,
        parallel_ledger_id: str,
        source_journal_id: str,
        account_id: str,
        debit_amount: float,
        credit_amount: float,
        posting_date: str,
        fiscal_period_id: str | None = None,
    ) -> dict:
        eid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.parallel_ledger_entries (
                      id, org_id, parallel_ledger_id, source_journal_id, account_id,
                      debit_amount, credit_amount, posting_date, fiscal_period_id
                    )
                    VALUES (
                      %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid,
                      %s, %s, %s::date, %s::uuid
                    )
                    RETURNING id::text, parallel_ledger_id::text, source_journal_id::text,
                              account_id::text, debit_amount::float8, credit_amount::float8,
                              posting_date::text
                    """,
                    (
                        eid,
                        org_id,
                        parallel_ledger_id,
                        source_journal_id,
                        account_id,
                        debit_amount,
                        credit_amount,
                        posting_date,
                        fiscal_period_id,
                    ),
                )
                return dict(cur.fetchone() or {"id": eid})

    def list_entries(
        self,
        org_id: str,
        *,
        parallel_ledger_id: str,
        source_journal_id: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        limit = max(1, min(int(limit or 200), 500))
        where = ["org_id = %s::uuid", "parallel_ledger_id = %s::uuid"]
        params: list = [org_id, parallel_ledger_id]
        if source_journal_id:
            where.append("source_journal_id = %s::uuid")
            params.append(source_journal_id)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, parallel_ledger_id::text, source_journal_id::text,
                           account_id::text, debit_amount::float8, credit_amount::float8,
                           posting_date::text, fiscal_period_id::text, created_at::text
                    FROM erp.parallel_ledger_entries
                    WHERE {' AND '.join(where)}
                    ORDER BY posting_date DESC, created_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def has_entries_for_journal(self, org_id: str, *, parallel_ledger_id: str, journal_id: str) -> bool:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM erp.parallel_ledger_entries
                    WHERE org_id = %s::uuid AND parallel_ledger_id = %s::uuid
                      AND source_journal_id = %s::uuid
                    LIMIT 1
                    """,
                    (org_id, parallel_ledger_id, journal_id),
                )
                return cur.fetchone() is not None


parallel_ledger_repository = ParallelLedgerRepository()
