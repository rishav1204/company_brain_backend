from typing import Any

from app.services.db import get_db_conn, set_rls_org


class SodConflictRepository:
    def list_conflicts(self, org_id: str, *, active_only: bool = True) -> list[dict[str, Any]]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if active_only:
                    cur.execute(
                        """
                        SELECT id::text AS id, role_a, role_b, scope, description, active, created_at
                        FROM governance.sod_conflicts
                        WHERE org_id = %s::uuid AND active = TRUE
                        ORDER BY role_a, role_b
                        """,
                        (org_id,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text AS id, role_a, role_b, scope, description, active, created_at
                        FROM governance.sod_conflicts
                        WHERE org_id = %s::uuid
                        ORDER BY role_a, role_b
                        """,
                        (org_id,),
                    )
                return list(cur.fetchall())

    def upsert_conflict(
        self,
        org_id: str,
        *,
        role_a: str,
        role_b: str,
        scope: str = "org",
        description: str | None = None,
    ) -> dict[str, Any]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO governance.sod_conflicts (org_id, role_a, role_b, scope, description)
                    VALUES (%s::uuid, %s, %s, %s, %s)
                    ON CONFLICT (org_id, role_a, role_b, scope) DO UPDATE SET
                        description = EXCLUDED.description,
                        active = TRUE,
                        updated_at = NOW()
                    RETURNING id::text AS id, role_a, role_b, scope, description, active
                    """,
                    (org_id, role_a, role_b, scope, description),
                )
                return cur.fetchone()

    def deactivate(self, org_id: str, conflict_id: str) -> bool:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE governance.sod_conflicts SET active = FALSE, updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id
                    """,
                    (org_id, conflict_id),
                )
                return cur.fetchone() is not None


sod_conflict_repo = SodConflictRepository()
