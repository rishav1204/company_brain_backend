from typing import Any

from app.services.db import get_db_conn, set_rls_org


class DepartmentRepository:
    def list_departments(self, org_id: str) -> list[dict[str, Any]]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, department_code, department_name, status, created_at
                    FROM core.departments
                    WHERE org_id = %s::uuid
                    ORDER BY department_name
                    """,
                    (org_id,),
                )
                return list(cur.fetchall())

    def create_department(
        self,
        org_id: str,
        department_code: str,
        department_name: str,
    ) -> dict[str, Any]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO core.departments (org_id, department_code, department_name)
                    VALUES (%s::uuid, %s, %s)
                    RETURNING id::text AS id, department_code, department_name, status
                    """,
                    (org_id, department_code.strip(), department_name.strip()),
                )
                return cur.fetchone()

    def get_by_id(self, org_id: str, department_id: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, department_code, department_name, status
                    FROM core.departments
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, department_id),
                )
                return cur.fetchone()


department_repo = DepartmentRepository()
