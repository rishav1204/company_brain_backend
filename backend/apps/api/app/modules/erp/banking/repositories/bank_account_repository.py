from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class BankAccountRepository:
    def create(
        self,
        org_id: str,
        *,
        account_name: str,
        bank_name: str,
        account_number_encrypted: str,
        ifsc_code: str,
        currency_code: str,
        account_type: str,
        ledger_account_id: str | None,
        company_id: str | None,
        created_by: str | None,
        metadata: dict | None = None,
    ) -> dict:
        aid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.bank_accounts (
                      id, org_id, company_id, account_name, bank_name, account_number_encrypted,
                      ifsc_code, currency_code, account_type, ledger_account_id, created_by, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s,%s,%s,%s,%s,%s::uuid,%s::uuid,%s::jsonb)
                    RETURNING id::text, account_name, bank_name, ifsc_code, currency_code,
                              account_type, ledger_account_id::text, is_active, created_at::text
                    """,
                    (
                        aid, org_id, company_id, account_name, bank_name, account_number_encrypted,
                        ifsc_code, currency_code, account_type, ledger_account_id, created_by, Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": aid})

    def get(self, org_id: str, *, bank_account_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, company_id::text, account_name, bank_name, account_number_encrypted,
                           ifsc_code, currency_code, account_type, ledger_account_id::text, is_active,
                           COALESCE(opening_balance, 0) AS opening_balance,
                           metadata, created_by::text, created_at::text, updated_at::text
                    FROM erp.bank_accounts
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, bank_account_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(self, org_id: str, *, active_only: bool = True, limit: int = 200) -> list[dict]:
        limit = max(1, min(limit, 500))
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
                    SELECT id::text, account_name, bank_name, ifsc_code, currency_code, account_type,
                           ledger_account_id::text, is_active, COALESCE(opening_balance, 0) AS opening_balance, created_at::text
                    FROM erp.bank_accounts
                    WHERE {' AND '.join(where)}
                    ORDER BY account_name ASC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def update(
        self,
        org_id: str,
        *,
        bank_account_id: str,
        account_name: str | None = None,
        is_active: bool | None = None,
        ledger_account_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        fields: list[str] = ["updated_at = NOW()"]
        params: list = []
        if account_name is not None:
            fields.append("account_name = %s")
            params.append(account_name)
        if is_active is not None:
            fields.append("is_active = %s")
            params.append(is_active)
        if ledger_account_id is not None:
            fields.append("ledger_account_id = %s::uuid")
            params.append(ledger_account_id)
        if metadata is not None:
            fields.append("metadata = %s::jsonb")
            params.append(Json(metadata))
        params.extend([org_id, bank_account_id])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE erp.bank_accounts SET {', '.join(fields)}
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, account_name, is_active, ledger_account_id::text
                    """,
                    tuple(params),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Bank account not found")
                return dict(row)

    def get_by_ledger_account(self, org_id: str, *, ledger_account_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, ledger_account_id::text, account_name, is_active
                    FROM erp.bank_accounts
                    WHERE org_id = %s::uuid AND ledger_account_id = %s::uuid AND is_active = true
                    LIMIT 1
                    """,
                    (org_id, ledger_account_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None


bank_account_repository = BankAccountRepository()
