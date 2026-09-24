from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class AnomalyRepository:
    def create(self, org_id: str, *, data: dict) -> dict:
        anomaly_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_os.invoice_anomalies (
                        id, org_id, extraction_id, invoice_id, anomaly_type, anomaly_score,
                        severity, description, status, metadata
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s::jsonb
                    )
                    RETURNING id::text, extraction_id::text AS extraction_id, anomaly_type,
                              anomaly_score::float8 AS anomaly_score, severity, description, status
                    """,
                    (
                        anomaly_id,
                        org_id,
                        data.get("extraction_id"),
                        data.get("invoice_id"),
                        data["anomaly_type"],
                        data.get("anomaly_score", 0),
                        data.get("severity", "medium"),
                        data["description"],
                        data.get("status", "open"),
                        Json(data.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {})

    def list_for_extraction(self, org_id: str, extraction_id: str, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, extraction_id::text AS extraction_id, anomaly_type,
                           anomaly_score::float8 AS anomaly_score, severity, description, status
                    FROM finance_os.invoice_anomalies
                    WHERE org_id = %s::uuid AND extraction_id = %s::uuid
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (org_id, extraction_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]

    def list_recent(self, org_id: str, limit: int = 200) -> list[dict]:
        limit = clamp_limit(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, extraction_id::text AS extraction_id, anomaly_type,
                           anomaly_score::float8 AS anomaly_score, severity, description, status
                    FROM finance_os.invoice_anomalies
                    WHERE org_id = %s::uuid
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]
