from __future__ import annotations

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class AccountUsageRepository:
    def get_or_default(self, org_id: str, *, account_id: str) -> dict:
        # Prefer GL-backed truth if Module 9 tables exist.
        gl_usage = self.get_gl_usage(org_id, account_id=account_id)
        if gl_usage is not None:
            return gl_usage
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, has_balance, used_in_journals, last_seen_at::text
                    FROM erp.account_usage
                    WHERE org_id = %s::uuid AND account_id = %s::uuid
                    """,
                    (org_id, account_id),
                )
                row = cur.fetchone()
                if row:
                    return dict(row)
        return {"id": None, "has_balance": False, "used_in_journals": False}

    def get_gl_usage(self, org_id: str, *, account_id: str) -> dict | None:
        """
        If GL tables exist, derive usage from ledger/balances:
        - used_in_journals: any ledger_entry exists for account
        - has_balance: any non-zero projection exists
        """
        try:
            with get_db_conn() as conn:
                set_rls_org(conn, org_id)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT to_regclass('erp.ledger_entries') IS NOT NULL AS has_le,
                               to_regclass('erp.account_balances') IS NOT NULL AS has_ab
                        """
                    )
                    flags = cur.fetchone() or {}
                    if not flags.get("has_le") or not flags.get("has_ab"):
                        return None
                    cur.execute(
                        """
                        SELECT EXISTS(
                          SELECT 1 FROM erp.ledger_entries
                          WHERE org_id = %s::uuid AND account_id = %s::uuid
                          LIMIT 1
                        ) AS used_in_journals
                        """,
                        (org_id, account_id),
                    )
                    used = bool((cur.fetchone() or {}).get("used_in_journals"))
                    cur.execute(
                        """
                        SELECT EXISTS(
                          SELECT 1 FROM erp.account_balances
                          WHERE org_id = %s::uuid AND account_id = %s::uuid
                            AND (ABS(COALESCE(closing_balance, 0)) > 0.0001
                              OR ABS(COALESCE(debit_total, 0)) > 0.0001
                              OR ABS(COALESCE(credit_total, 0)) > 0.0001)
                          LIMIT 1
                        ) AS has_balance
                        """,
                        (org_id, account_id),
                    )
                    has_balance = bool((cur.fetchone() or {}).get("has_balance"))
                    return {"id": None, "has_balance": has_balance, "used_in_journals": used, "source": "gl"}
        except Exception:
            return None

    def upsert(self, org_id: str, *, account_id: str, has_balance: bool, used_in_journals: bool) -> dict:
        rid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.account_usage (id, org_id, account_id, has_balance, used_in_journals, last_seen_at)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, NOW())
                    ON CONFLICT (org_id, account_id) DO UPDATE
                    SET has_balance = EXCLUDED.has_balance,
                        used_in_journals = EXCLUDED.used_in_journals,
                        last_seen_at = NOW()
                    RETURNING id::text, has_balance, used_in_journals, last_seen_at::text
                    """,
                    (rid, org_id, account_id, bool(has_balance), bool(used_in_journals)),
                )
                return dict(cur.fetchone() or {"id": rid})


account_usage_repository = AccountUsageRepository()

