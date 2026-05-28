from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class ViolationRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'governance' AND table_name = 'violations'
                        LIMIT 1
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def record(
        self,
        org_id: str,
        *,
        violation_type: str,
        severity: str,
        detected_by: str,
        details: dict,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> dict[str, Any]:
        vid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO governance.violations (
                        id, org_id, violation_type, severity, entity_type, entity_id,
                        detected_by, details
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s::uuid, %s, %s::jsonb)
                    RETURNING id::text, violation_type, severity, resolved, created_at
                    """,
                    (vid, org_id, violation_type, severity, entity_type, entity_id, detected_by, Json(details)),
                )
                return dict(cur.fetchone() or {})

    def resolve(self, org_id: str, violation_id: str, *, resolved_by: str) -> dict[str, Any]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE governance.violations
                    SET resolved = TRUE, resolved_at = NOW(), resolved_by = %s::uuid
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    RETURNING id::text, violation_type, resolved, resolved_at
                    """,
                    (resolved_by, violation_id, org_id),
                )
                return dict(cur.fetchone() or {})

    def list_open(self, org_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        if not self.schema_ready():
            return []
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, violation_type, severity, entity_type, entity_id::text,
                           detected_by, details, resolved, created_at
                    FROM governance.violations
                    WHERE org_id = %s::uuid AND resolved = FALSE
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return [dict(row) for row in cur.fetchall()]


violation_repository = ViolationRepository()
