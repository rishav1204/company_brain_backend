from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class SnapshotRepository:
    def upsert(self, org_id: str, *, data: dict) -> dict:
        snap_id = data.get("id") or str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_os.workflow_snapshots (
                        id, org_id, workflow_instance_id, workflow_definition_id, workflow_type,
                        entity_type, entity_id, started_at, completed_at, duration_seconds,
                        status, efficiency_score, health_score, metadata
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s::uuid,
                        %s::timestamptz, %s::timestamptz, %s, %s, %s, %s, %s::jsonb
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        completed_at = EXCLUDED.completed_at,
                        duration_seconds = EXCLUDED.duration_seconds,
                        status = EXCLUDED.status,
                        efficiency_score = EXCLUDED.efficiency_score,
                        health_score = EXCLUDED.health_score,
                        metadata = EXCLUDED.metadata
                    RETURNING id::text, workflow_instance_id::text AS workflow_instance_id,
                              workflow_type, status, efficiency_score::float8 AS efficiency_score,
                              duration_seconds, created_at::text
                    """,
                    (
                        snap_id,
                        org_id,
                        data["workflow_instance_id"],
                        data.get("workflow_definition_id"),
                        data["workflow_type"],
                        data.get("entity_type"),
                        data.get("entity_id"),
                        data.get("started_at"),
                        data.get("completed_at"),
                        data.get("duration_seconds", 0),
                        data.get("status", "running"),
                        data.get("efficiency_score", 0),
                        data.get("health_score"),
                        Json(data.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {})

    def get_by_instance(self, org_id: str, workflow_instance_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, workflow_instance_id::text AS workflow_instance_id,
                           workflow_type, status, efficiency_score::float8 AS efficiency_score,
                           duration_seconds, health_score::float8 AS health_score, metadata,
                           started_at::text AS started_at, completed_at::text AS completed_at
                    FROM finance_os.workflow_snapshots
                    WHERE org_id = %s::uuid AND workflow_instance_id = %s::uuid
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (org_id, workflow_instance_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list_recent(self, org_id: str, *, workflow_type: str | None = None, limit: int = 100) -> list[dict]:
        limit = max(1, min(limit, 500))
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if workflow_type:
            where.append("workflow_type = %s")
            params.append(workflow_type)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, workflow_instance_id::text AS workflow_instance_id,
                           workflow_type, status, efficiency_score::float8 AS efficiency_score,
                           duration_seconds
                    FROM finance_os.workflow_snapshots
                    WHERE {' AND '.join(where)}
                    ORDER BY created_at DESC LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in cur.fetchall()]


snapshot_repository = SnapshotRepository()
