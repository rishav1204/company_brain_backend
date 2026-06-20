from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class PredictionRepository:
    def create(self, org_id: str, *, data: dict) -> dict:
        prediction_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_os.invoice_predictions (
                        id, org_id, extraction_id, prediction_type, suggested_account_id,
                        suggested_gst_code, suggested_cost_center, confidence_score, metadata
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s::uuid, %s, %s::uuid, %s, %s::uuid, %s, %s::jsonb
                    )
                    RETURNING id::text, extraction_id::text AS extraction_id, prediction_type,
                              suggested_account_id::text AS suggested_account_id,
                              suggested_gst_code, confidence_score::float8 AS confidence_score,
                              metadata, created_at::text
                    """,
                    (
                        prediction_id,
                        org_id,
                        data["extraction_id"],
                        data.get("prediction_type", "ledger"),
                        data.get("suggested_account_id"),
                        data.get("suggested_gst_code"),
                        data.get("suggested_cost_center"),
                        data.get("confidence_score", 0),
                        Json(data.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {})

    def list_for_extraction(self, org_id: str, extraction_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, extraction_id::text AS extraction_id, prediction_type,
                           suggested_account_id::text AS suggested_account_id,
                           suggested_gst_code, confidence_score::float8 AS confidence_score,
                           metadata, created_at::text
                    FROM finance_os.invoice_predictions
                    WHERE org_id = %s::uuid AND extraction_id = %s::uuid
                    ORDER BY created_at DESC
                    """,
                    (org_id, extraction_id),
                )
                return [dict(r) for r in cur.fetchall()]

    def update(self, org_id: str, prediction_id: str, *, data: dict) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE finance_os.invoice_predictions
                    SET suggested_account_id = COALESCE(%s::uuid, suggested_account_id),
                        suggested_gst_code = COALESCE(%s, suggested_gst_code),
                        metadata = metadata || %s::jsonb
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, extraction_id::text AS extraction_id, prediction_type,
                              suggested_account_id::text AS suggested_account_id,
                              suggested_gst_code, confidence_score::float8 AS confidence_score,
                              metadata
                    """,
                    (
                        data.get("suggested_account_id"),
                        data.get("suggested_gst_code"),
                        Json(data.get("metadata") or {}),
                        org_id,
                        prediction_id,
                    ),
                )
                row = cur.fetchone()
                return dict(row) if row else None
