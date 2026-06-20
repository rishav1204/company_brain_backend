from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class DuplicateRepository:
    def create(self, org_id: str, *, data: dict) -> dict:
        score_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_os.invoice_duplicate_scores (
                        id, org_id, extraction_id, matched_invoice_id, similarity_score,
                        status, score_breakdown
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s::jsonb
                    )
                    RETURNING id::text, extraction_id::text AS extraction_id,
                              matched_invoice_id::text AS matched_invoice_id,
                              similarity_score::float8 AS similarity_score, status, score_breakdown
                    """,
                    (
                        score_id,
                        org_id,
                        data["extraction_id"],
                        data.get("matched_invoice_id"),
                        data.get("similarity_score", 0),
                        data.get("status", "clean"),
                        Json(data.get("score_breakdown") or {}),
                    ),
                )
                return dict(cur.fetchone() or {})

    def latest_for_extraction(self, org_id: str, extraction_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, extraction_id::text AS extraction_id,
                           matched_invoice_id::text AS matched_invoice_id,
                           similarity_score::float8 AS similarity_score, status, score_breakdown
                    FROM finance_os.invoice_duplicate_scores
                    WHERE org_id = %s::uuid AND extraction_id = %s::uuid
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (org_id, extraction_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def update_status(
        self,
        org_id: str,
        extraction_id: str,
        *,
        status: str,
        matched_invoice_id: str | None = None,
    ) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE finance_os.invoice_duplicate_scores
                    SET status = %s,
                        matched_invoice_id = COALESCE(%s::uuid, matched_invoice_id)
                    WHERE org_id = %s::uuid AND extraction_id = %s::uuid
                      AND id = (
                        SELECT id FROM finance_os.invoice_duplicate_scores
                        WHERE org_id = %s::uuid AND extraction_id = %s::uuid
                        ORDER BY created_at DESC LIMIT 1
                      )
                    RETURNING id::text, extraction_id::text AS extraction_id,
                              matched_invoice_id::text AS matched_invoice_id,
                              similarity_score::float8 AS similarity_score, status, score_breakdown
                    """,
                    (status, matched_invoice_id, org_id, extraction_id, org_id, extraction_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None
