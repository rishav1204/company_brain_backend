from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class EvidenceRepository:
    def link_document(
        self,
        org_id: str,
        *,
        document_id: str,
        entity_type: str,
        entity_id: str,
        workflow_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        link_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents.evidence_links (
                        id, org_id, document_id, entity_type, entity_id, workflow_id, metadata
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s::uuid, %s::uuid, %s::jsonb)
                    RETURNING id::text, document_id::text AS document_id, entity_type, entity_id::text AS entity_id,
                              workflow_id::text AS workflow_id, metadata, created_at::text
                    """,
                    (link_id, org_id, document_id, entity_type, entity_id, workflow_id, Json(metadata or {})),
                )
                return dict(cur.fetchone() or {})

    def list_for_entity(self, org_id: str, *, entity_type: str, entity_id: str, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, document_id::text AS document_id, entity_type, entity_id::text AS entity_id,
                           workflow_id::text AS workflow_id, metadata, created_at::text
                    FROM documents.evidence_links
                    WHERE org_id = %s::uuid AND entity_type = %s AND entity_id = %s::uuid
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (org_id, entity_type, entity_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]

    def create_duplicate_candidate(
        self,
        org_id: str,
        *,
        document_id: str,
        matched_document_id: str,
        duplicate_reason: str,
        similarity_score: float,
    ) -> dict:
        duplicate_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents.duplicate_candidates (
                        id, org_id, document_id, matched_document_id, duplicate_reason, similarity_score
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s)
                    RETURNING id::text, document_id::text AS document_id,
                              matched_document_id::text AS matched_document_id, duplicate_reason,
                              similarity_score::float8 AS similarity_score, status, created_at::text
                    """,
                    (duplicate_id, org_id, document_id, matched_document_id, duplicate_reason, similarity_score),
                )
                return dict(cur.fetchone() or {})


evidence_repository = EvidenceRepository()
