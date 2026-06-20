from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class PredictionRepository:
    def create(self, org_id: str, *, data: dict) -> dict:
        pred_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_os.workflow_predictions (
                        id, org_id, workflow_instance_id, prediction_type,
                        predicted_value, confidence_score, metadata
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::jsonb)
                    RETURNING id::text, workflow_instance_id::text AS workflow_instance_id,
                              prediction_type, predicted_value, confidence_score::float8 AS confidence_score
                    """,
                    (
                        pred_id,
                        org_id,
                        data["workflow_instance_id"],
                        data["prediction_type"],
                        data["predicted_value"],
                        data.get("confidence_score", 0),
                        Json(data.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {})

    def list_for_instance(self, org_id: str, workflow_instance_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, prediction_type, predicted_value,
                           confidence_score::float8 AS confidence_score, metadata, created_at::text
                    FROM finance_os.workflow_predictions
                    WHERE org_id = %s::uuid AND workflow_instance_id = %s::uuid
                    ORDER BY created_at DESC
                    """,
                    (org_id, workflow_instance_id),
                )
                return [dict(r) for r in cur.fetchall()]

    def list_sla_risks(self, org_id: str, *, limit: int = 50) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, workflow_instance_id::text AS workflow_instance_id,
                           prediction_type, predicted_value, confidence_score::float8 AS confidence_score,
                           metadata, created_at::text
                    FROM finance_os.workflow_predictions
                    WHERE org_id = %s::uuid AND prediction_type = 'sla_breach_risk'
                    ORDER BY created_at DESC LIMIT %s
                    """,
                    (org_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]

    def update(self, org_id: str, prediction_id: str, *, data: dict) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE finance_os.workflow_predictions
                    SET predicted_value = COALESCE(%s, predicted_value),
                        metadata = metadata || %s::jsonb
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, prediction_type, predicted_value, confidence_score::float8 AS confidence_score
                    """,
                    (
                        data.get("predicted_value"),
                        Json(data.get("metadata") or {}),
                        org_id,
                        prediction_id,
                    ),
                )
                row = cur.fetchone()
                return dict(row) if row else None


prediction_repository = PredictionRepository()
