from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class EmployeeRepository:
    def create(
        self,
        org_id: str,
        *,
        employee_code: str,
        pan: str,
        name: str,
        date_of_joining: str | None = None,
        company_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        eid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.payroll_employees (
                      id, org_id, company_id, employee_code, pan, name, date_of_joining, metadata
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::date, %s::jsonb)
                    ON CONFLICT (org_id, employee_code) DO UPDATE
                      SET pan = EXCLUDED.pan, name = EXCLUDED.name,
                          date_of_joining = EXCLUDED.date_of_joining,
                          company_id = EXCLUDED.company_id,
                          metadata = EXCLUDED.metadata,
                          status = 'active'
                    RETURNING id::text, employee_code, pan, name, date_of_joining::text,
                              status, company_id::text, created_at::text
                    """,
                    (eid, org_id, company_id, employee_code, pan.upper(), name, date_of_joining, Json(metadata or {})),
                )
                return dict(cur.fetchone() or {"id": eid})

    def get(self, org_id: str, *, employee_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, employee_code, pan, name, date_of_joining::text,
                           status, company_id::text, metadata, created_at::text
                    FROM erp.payroll_employees
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, employee_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def get_by_code(self, org_id: str, *, employee_code: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, employee_code, pan, name, date_of_joining::text,
                           status, company_id::text, metadata, created_at::text
                    FROM erp.payroll_employees
                    WHERE org_id = %s::uuid AND employee_code = %s
                    """,
                    (org_id, employee_code),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(self, org_id: str, *, status: str | None = "active", limit: int = 200) -> list[dict]:
        limit = max(1, min(int(limit or 200), 500))
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
                    SELECT id::text, employee_code, pan, name, date_of_joining::text,
                           status, company_id::text, created_at::text
                    FROM erp.payroll_employees
                    WHERE {' AND '.join(where)}
                    ORDER BY employee_code ASC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def update(
        self,
        org_id: str,
        *,
        employee_id: str,
        name: str | None = None,
        pan: str | None = None,
        date_of_joining: str | None = None,
        status: str | None = None,
        metadata: dict | None = None,
    ) -> dict | None:
        sets: list[str] = []
        params: list = []
        if name is not None:
            sets.append("name = %s")
            params.append(name)
        if pan is not None:
            sets.append("pan = %s")
            params.append(pan.upper())
        if date_of_joining is not None:
            sets.append("date_of_joining = %s::date")
            params.append(date_of_joining)
        if status is not None:
            sets.append("status = %s")
            params.append(status)
        if metadata is not None:
            sets.append("metadata = %s::jsonb")
            params.append(Json(metadata))
        if not sets:
            return self.get(org_id, employee_id=employee_id)
        params.extend([org_id, employee_id])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE erp.payroll_employees
                    SET {', '.join(sets)}
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, employee_code, pan, name, date_of_joining::text,
                              status, company_id::text, created_at::text
                    """,
                    tuple(params),
                )
                row = cur.fetchone()
                return dict(row) if row else None


employee_repository = EmployeeRepository()
