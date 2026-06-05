from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class VendorRepository:
    def create(
        self,
        org_id: str,
        *,
        vendor_code: str,
        vendor_name: str,
        gstin: str | None = None,
        pan: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        payment_terms_days: int = 30,
        payable_account_id: str | None = None,
        company_id: str | None = None,
        created_by: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        vid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.vendors (
                      id, org_id, company_id, vendor_code, vendor_name, gstin, pan,
                      email, phone, payment_terms_days, payable_account_id, created_by, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s,%s,%s,%s,%s,%s,%s::uuid,%s::uuid,%s::jsonb)
                    RETURNING id::text, vendor_code, vendor_name, gstin, pan, email, phone,
                              payment_terms_days, status, payable_account_id::text, company_id::text,
                              created_at::text
                    """,
                    (
                        vid, org_id, company_id, vendor_code, vendor_name,
                        gstin, pan, email, phone, payment_terms_days,
                        payable_account_id, created_by, Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": vid})

    def get(self, org_id: str, *, vendor_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, vendor_code, vendor_name, gstin, pan, email, phone,
                           payment_terms_days, status, payable_account_id::text, company_id::text,
                           metadata, created_by::text, created_at::text, updated_at::text
                    FROM erp.vendors
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, vendor_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(self, org_id: str, *, status: str | None = None, limit: int = 100) -> list[dict]:
        limit = max(1, min(limit, 500))
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if status:
            where.append("status = %s")
            params.append(status)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, vendor_code, vendor_name, gstin, status, payment_terms_days, created_at::text
                    FROM erp.vendors
                    WHERE {' AND '.join(where)}
                    ORDER BY vendor_name ASC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def update(
        self,
        org_id: str,
        *,
        vendor_id: str,
        vendor_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        payment_terms_days: int | None = None,
        payable_account_id: str | None = None,
        status: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        fields: list[str] = []
        params: list = []
        if vendor_name is not None:
            fields.append("vendor_name = %s")
            params.append(vendor_name)
        if email is not None:
            fields.append("email = %s")
            params.append(email)
        if phone is not None:
            fields.append("phone = %s")
            params.append(phone)
        if payment_terms_days is not None:
            fields.append("payment_terms_days = %s")
            params.append(payment_terms_days)
        if payable_account_id is not None:
            fields.append("payable_account_id = %s::uuid")
            params.append(payable_account_id)
        if status is not None:
            fields.append("status = %s")
            params.append(status)
        if metadata is not None:
            fields.append("metadata = %s::jsonb")
            params.append(Json(metadata))
        if not fields:
            row = self.get(org_id, vendor_id=vendor_id)
            if not row:
                raise ValueError("Vendor not found")
            return row
        fields.append("updated_at = NOW()")
        params.extend([org_id, vendor_id])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE erp.vendors
                    SET {', '.join(fields)}
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, vendor_code, vendor_name, gstin, pan, email, phone,
                              payment_terms_days, status, payable_account_id::text, company_id::text,
                              metadata, created_at::text, updated_at::text
                    """,
                    tuple(params),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Vendor not found")
                return dict(row)

    def find_by_gstin(self, org_id: str, *, gstin: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, vendor_code, vendor_name, gstin
                    FROM erp.vendors
                    WHERE org_id = %s::uuid AND gstin = %s
                    LIMIT 1
                    """,
                    (org_id, gstin.upper()),
                )
                row = cur.fetchone()
                return dict(row) if row else None


vendor_repository = VendorRepository()
