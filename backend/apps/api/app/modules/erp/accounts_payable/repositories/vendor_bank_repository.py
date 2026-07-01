from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class VendorBankRepository:
    def create(
        self,
        org_id: str,
        *,
        vendor_id: str,
        account_number_encrypted: str,
        ifsc_code: str,
        bank_name: str | None = None,
        is_primary: bool = False,
    ) -> dict:
        bid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if is_primary:
                    cur.execute(
                        "UPDATE erp.vendor_bank_accounts SET is_primary = false WHERE org_id = %s::uuid AND vendor_id = %s::uuid",
                        (org_id, vendor_id),
                    )
                cur.execute(
                    """
                    INSERT INTO erp.vendor_bank_accounts (
                      id, org_id, vendor_id, account_number_encrypted, ifsc_code, bank_name, is_primary
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s,%s,%s)
                    RETURNING id::text, vendor_id::text, ifsc_code, bank_name, is_primary, verified, created_at::text
                    """,
                    (bid, org_id, vendor_id, account_number_encrypted, ifsc_code, bank_name, is_primary),
                )
                return dict(cur.fetchone() or {"id": bid})

    def get(self, org_id: str, *, bank_account_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, vendor_id::text, ifsc_code, bank_name, is_primary, verified, created_at::text
                    FROM erp.vendor_bank_accounts
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, bank_account_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list_by_vendor(self, org_id: str, *, vendor_id: str, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit, default=500, maximum=500)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, ifsc_code, bank_name, is_primary, verified, created_at::text
                    FROM erp.vendor_bank_accounts
                    WHERE org_id = %s::uuid AND vendor_id = %s::uuid
                    ORDER BY is_primary DESC, created_at ASC
                    LIMIT %s
                    """,
                    (org_id, vendor_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


vendor_bank_repository = VendorBankRepository()
