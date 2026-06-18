from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class CustomerRepository:
    def create(
        self,
        org_id: str,
        *,
        customer_code: str,
        customer_name: str,
        customer_type: str = "corporate",
        gstin: str | None = None,
        pan: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        credit_limit: float = 0,
        payment_terms_days: int = 30,
        receivable_account_id: str | None = None,
        revenue_account_id: str | None = None,
        company_id: str | None = None,
        created_by: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        cid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.customers (
                      id, org_id, company_id, customer_code, customer_name, customer_type,
                      gstin, pan, email, phone, credit_limit, payment_terms_days,
                      receivable_account_id, revenue_account_id, created_by, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s,%s,%s,%s,%s,%s,%s::numeric,%s,
                            %s::uuid,%s::uuid,%s::uuid,%s::jsonb)
                    RETURNING id::text, customer_code, customer_name, customer_type, gstin,
                              credit_limit, payment_terms_days, status, created_at::text
                    """,
                    (
                        cid, org_id, company_id, customer_code, customer_name, customer_type,
                        gstin, pan, email, phone, credit_limit, payment_terms_days,
                        receivable_account_id, revenue_account_id, created_by, Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": cid})

    def get(self, org_id: str, *, customer_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, customer_code, customer_name, customer_type, gstin, pan,
                           email, phone, credit_limit, payment_terms_days, status,
                           receivable_account_id::text, revenue_account_id::text, company_id::text,
                           metadata, created_by::text, created_at::text, updated_at::text
                    FROM erp.customers
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, customer_id),
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
                    SELECT id::text, customer_code, customer_name, customer_type, gstin,
                           credit_limit, status, payment_terms_days, created_at::text
                    FROM erp.customers
                    WHERE {' AND '.join(where)}
                    ORDER BY customer_name ASC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def update(
        self,
        org_id: str,
        *,
        customer_id: str,
        customer_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        credit_limit: float | None = None,
        payment_terms_days: int | None = None,
        receivable_account_id: str | None = None,
        revenue_account_id: str | None = None,
        status: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        fields: list[str] = []
        params: list = []
        for col, val in (
            ("customer_name", customer_name),
            ("email", email),
            ("phone", phone),
            ("payment_terms_days", payment_terms_days),
            ("status", status),
        ):
            if val is not None:
                fields.append(f"{col} = %s")
                params.append(val)
        if credit_limit is not None:
            fields.append("credit_limit = %s::numeric")
            params.append(credit_limit)
        if receivable_account_id is not None:
            fields.append("receivable_account_id = %s::uuid")
            params.append(receivable_account_id)
        if revenue_account_id is not None:
            fields.append("revenue_account_id = %s::uuid")
            params.append(revenue_account_id)
        if metadata is not None:
            fields.append("metadata = %s::jsonb")
            params.append(Json(metadata))
        if not fields:
            row = self.get(org_id, customer_id=customer_id)
            if not row:
                raise ValueError("Customer not found")
            return row
        fields.append("updated_at = NOW()")
        params.extend([org_id, customer_id])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE erp.customers SET {', '.join(fields)}
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, customer_name, credit_limit, status, metadata
                    """,
                    tuple(params),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Customer not found")
                return dict(row)


customer_repository = CustomerRepository()
