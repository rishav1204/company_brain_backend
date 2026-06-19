from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class CandidateRepository:
    def create(
        self,
        org_id: str,
        *,
        source_type: str,
        source_id: str,
        amount: float,
        description: str | None = None,
        suggested_category_id: str | None = None,
        status: str = "pending",
        metadata: dict | None = None,
    ) -> dict:
        cid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.asset_capitalization_candidates (
                      id, org_id, source_type, source_id, amount, description,
                      suggested_category_id, status, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s,%s::uuid,%s::numeric,%s,%s::uuid,%s,%s::jsonb)
                    RETURNING id::text, status
                    """,
                    (
                        cid, org_id, source_type, source_id, amount, description,
                        suggested_category_id, status, Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": cid})

    def get(self, org_id: str, *, candidate_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, source_type, source_id::text, amount, description,
                           suggested_category_id::text, status, asset_id::text, metadata
                    FROM erp.asset_capitalization_candidates
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, candidate_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(self, org_id: str, *, status: str | None = None, limit: int = 100) -> list[dict]:
        clauses = ["org_id = %s::uuid"]
        params: list = [org_id]
        if status:
            clauses.append("status = %s")
            params.append(status)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, source_type, source_id::text, amount, description, status
                    FROM erp.asset_capitalization_candidates
                    WHERE {' AND '.join(clauses)}
                    ORDER BY created_at DESC LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in cur.fetchall()]

    def set_converted(self, org_id: str, *, candidate_id: str, asset_id: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.asset_capitalization_candidates
                    SET status = 'converted', asset_id = %s::uuid, updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, asset_id::text, status
                    """,
                    (asset_id, org_id, candidate_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {}


candidate_repository = CandidateRepository()
