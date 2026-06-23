from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from typing import Any
from uuid import uuid4

from app.modules.finance_os.audit_explorer.repositories.schema_repository import audit_schema_repository
from app.services.db import get_db_conn, set_rls_org


class AuditEvidenceRepository:
    def schema_ready(self) -> bool:
        return audit_schema_repository.schema_ready()

    def link(
        self,
        org_id: str,
        *,
        timeline_id: str,
        evidence_type: str,
        evidence_ref: str,
        governance_evidence_id: str | None = None,
    ) -> dict[str, Any]:
        if not self.schema_ready():
            return {"id": "skipped"}
        row_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_audit.audit_evidence (
                        id, org_id, timeline_id, evidence_type, evidence_ref, governance_evidence_id
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s::uuid)
                    RETURNING id::text, timeline_id::text, evidence_type, evidence_ref
                    """,
                    (row_id, org_id, timeline_id, evidence_type, evidence_ref, governance_evidence_id),
                )
                return dict(cur.fetchone() or {})

    def list_for_timeline(self, org_id: str, timeline_id: str, limit: int = 500) -> list[dict[str, Any]]:
        if not self.schema_ready():
            limit = clamp_limit(limit)
            return []
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, timeline_id::text, evidence_type, evidence_ref,
                           governance_evidence_id::text, created_at
                    FROM finance_audit.audit_evidence
                    WHERE org_id = %s::uuid AND timeline_id = %s::uuid
                    ORDER BY created_at ASC
                    LIMIT %s
                    """,
                    (org_id, timeline_id),
                )
                return [dict(r) for r in cur.fetchall()]

    def list_for_object(self, org_id: str, *, object_type: str, object_id: str, limit: int = 500) -> list[dict[str, Any]]:
        if not self.schema_ready():
            limit = clamp_limit(limit)
            return []
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.id::text, e.timeline_id::text, e.evidence_type, e.evidence_ref,
                           e.governance_evidence_id::text, e.created_at, t.event_type
                    FROM finance_audit.audit_evidence e
                    JOIN finance_audit.audit_timelines t ON t.id = e.timeline_id
                    WHERE e.org_id = %s::uuid AND t.object_type = %s AND t.object_id = %s::uuid
                    ORDER BY e.created_at ASC
                    LIMIT %s
                    """,
                    (org_id, object_type, object_id),
                )
                return [dict(r) for r in cur.fetchall()]


audit_evidence_repository = AuditEvidenceRepository()
