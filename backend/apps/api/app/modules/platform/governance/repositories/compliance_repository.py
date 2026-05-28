from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class ComplianceRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'compliance' AND table_name = 'compliance_events'
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
        compliance_type: str,
        status: str,
        severity: str = "info",
        related_entity_type: str | None = None,
        related_entity_id: str | None = None,
        details: dict | None = None,
    ) -> dict[str, Any]:
        event_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO compliance.compliance_events (
                        id, org_id, compliance_type, status, severity,
                        related_entity_type, related_entity_id, details
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s::uuid, %s::jsonb)
                    RETURNING id::text, compliance_type, status, severity, details, created_at
                    """,
                    (
                        event_id,
                        org_id,
                        compliance_type,
                        status,
                        severity,
                        related_entity_type,
                        related_entity_id,
                        Json(details or {}),
                    ),
                )
                return dict(cur.fetchone() or {})

    def list_events(
        self,
        org_id: str,
        *,
        compliance_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not self.schema_ready():
            return []
        clauses = ["org_id = %s::uuid"]
        params: list[Any] = [org_id]
        if compliance_type:
            clauses.append("compliance_type = %s")
            params.append(compliance_type)
        if status:
            clauses.append("status = %s")
            params.append(status)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, compliance_type, status, severity,
                           related_entity_type, related_entity_id::text, details, created_at
                    FROM compliance.compliance_events
                    WHERE {' AND '.join(clauses)}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(row) for row in cur.fetchall()]


compliance_repository = ComplianceRepository()
