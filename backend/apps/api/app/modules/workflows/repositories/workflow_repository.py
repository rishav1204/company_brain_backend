from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class WorkflowRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables
                            WHERE table_schema = 'workflow' AND table_name = 'workflow_instances'
                        ) AS ok
                        """
                    )
                    row = cur.fetchone()
                    return bool(row and row.get("ok"))
        except Exception:
            return False

    def get_definition_by_key(self, org_id: str, workflow_key: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, org_id::text AS org_id, workflow_key, name, version,
                           definition_json, is_active
                    FROM workflow.workflow_definitions
                    WHERE org_id = %s::uuid AND workflow_key = %s AND is_active = TRUE
                    ORDER BY version DESC
                    LIMIT 1
                    """,
                    (org_id, workflow_key),
                )
                return cur.fetchone()

    def list_definitions(self, org_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit or 200), 500))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, workflow_key, name, version, is_active, created_at
                    FROM workflow.workflow_definitions
                    WHERE org_id = %s::uuid
                    ORDER BY workflow_key, version DESC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return list(cur.fetchall())

    def create_instance(
        self,
        *,
        org_id: str,
        workflow_type: str,
        started_by: str | None,
        definition_id: str | None = None,
        entity_type: str = "workflow",
        entity_id: str | None = None,
        legacy_workflow_id: str | None = None,
        metadata: dict | None = None,
        status: str = "queued",
    ) -> dict[str, Any]:
        instance_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO workflow.workflow_instances (
                        id, org_id, workflow_definition_id, entity_type, entity_id,
                        legacy_workflow_id, workflow_type, status, started_by, metadata
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s::uuid, %s::uuid, %s, %s, %s::uuid, %s::jsonb)
                    RETURNING id::text AS id, org_id::text AS org_id, workflow_type, status,
                              started_by::text AS started_by, started_at, metadata
                    """,
                    (
                        instance_id,
                        org_id,
                        definition_id,
                        entity_type,
                        entity_id,
                        legacy_workflow_id,
                        workflow_type,
                        status,
                        started_by,
                        Json(metadata or {}),
                    ),
                )
                return cur.fetchone()

    def get_instance(self, org_id: str, instance_id: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, org_id::text AS org_id, workflow_definition_id::text AS workflow_definition_id,
                           entity_type, entity_id::text AS entity_id, legacy_workflow_id::text AS legacy_workflow_id,
                           workflow_type, status, priority, started_by::text AS started_by,
                           started_at, completed_at, current_step_id::text AS current_step_id, metadata
                    FROM workflow.workflow_instances
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, instance_id),
                )
                return cur.fetchone()

    def get_instance_by_legacy(self, org_id: str, legacy_workflow_id: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, org_id::text AS org_id, workflow_definition_id::text AS workflow_definition_id,
                           entity_type, entity_id::text AS entity_id, legacy_workflow_id::text AS legacy_workflow_id,
                           workflow_type, status, priority, started_by::text AS started_by,
                           started_at, completed_at, current_step_id::text AS current_step_id, metadata
                    FROM workflow.workflow_instances
                    WHERE org_id = %s::uuid AND legacy_workflow_id = %s::uuid
                    """,
                    (org_id, legacy_workflow_id),
                )
                return cur.fetchone()

    def list_instances(
        self,
        org_id: str,
        *,
        workflow_type: str | None = None,
        status: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit or 200), 500))
        offset = max(0, int(offset or 0))
        clauses = ["org_id = %s::uuid"]
        params: list[Any] = [org_id]
        if workflow_type:
            clauses.append("workflow_type = %s")
            params.append(workflow_type)
        if status:
            normalized = status.strip().lower()
            if normalized == "pending":
                clauses.append("status IN ('waiting_approval', 'running', 'queued')")
            else:
                clauses.append("status = %s")
                params.append(status)
        params.extend([limit, offset])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text AS id, workflow_type, status, started_by::text AS owner_user_id,
                           started_at, completed_at, legacy_workflow_id::text AS legacy_workflow_id, metadata
                    FROM workflow.workflow_instances
                    WHERE {' AND '.join(clauses)}
                    ORDER BY started_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(params),
                )
                return [dict(row) for row in cur.fetchall()]

    def update_instance_status(
        self,
        org_id: str,
        instance_id: str,
        status: str,
        *,
        current_step_id: str | None = None,
        metadata: dict | None = None,
        priority: str | None = None,
        completed: bool = False,
    ) -> dict[str, Any] | None:
        sets = ["status = %s", "updated_at = NOW()"]
        params: list[Any] = [status]
        if current_step_id is not None:
            sets.append("current_step_id = %s::uuid")
            params.append(current_step_id)
        if metadata is not None:
            sets.append("metadata = %s::jsonb")
            params.append(Json(metadata))
        if priority is not None:
            sets.append("priority = %s")
            params.append(priority)
        if completed:
            sets.append("completed_at = NOW()")
        params.extend([instance_id, org_id])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE workflow.workflow_instances SET {', '.join(sets)}
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    RETURNING id::text AS id, status, workflow_type, started_by::text AS owner_user_id,
                              started_at, completed_at, metadata
                    """,
                    tuple(params),
                )
                return cur.fetchone()

    def create_definition(
        self,
        *,
        org_id: str,
        workflow_key: str,
        name: str,
        description: str | None,
        definition_json: dict,
        version: int | None = None,
    ) -> dict[str, Any]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if version is None:
                    cur.execute(
                        """
                        SELECT COALESCE(MAX(version), 0) + 1 AS next_version
                        FROM workflow.workflow_definitions
                        WHERE org_id = %s::uuid AND workflow_key = %s
                        """,
                        (org_id, workflow_key),
                    )
                    version = int((cur.fetchone() or {}).get("next_version") or 1)
                cur.execute(
                    """
                    INSERT INTO workflow.workflow_definitions (
                        org_id, workflow_key, name, description, version, definition_json, is_active
                    )
                    VALUES (%s::uuid, %s, %s, %s, %s, %s::jsonb, TRUE)
                    RETURNING id::text AS id, workflow_key, name, version, is_active
                    """,
                    (org_id, workflow_key, name, description, version, Json(definition_json)),
                )
                return cur.fetchone()

    def set_definition_active(self, org_id: str, definition_id: str, *, is_active: bool) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE workflow.workflow_definitions
                    SET is_active = %s, updated_at = NOW()
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    RETURNING id::text AS id, workflow_key, version, is_active
                    """,
                    (is_active, definition_id, org_id),
                )
                return cur.fetchone()

    def state_counts(self, org_id: str) -> dict[str, int]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*)::int AS total,
                        SUM(CASE WHEN status IN ('running', 'escalated') THEN 1 ELSE 0 END)::int AS blocked_count,
                        SUM(CASE WHEN status = 'waiting_approval' THEN 1 ELSE 0 END)::int AS pending_approval_count
                    FROM workflow.workflow_instances
                    WHERE org_id = %s::uuid
                    """,
                    (org_id,),
                )
                row = cur.fetchone() or {}
                return {
                    "total": int(row.get("total") or 0),
                    "blocked_count": int(row.get("blocked_count") or 0),
                    "pending_approval_count": int(row.get("pending_approval_count") or 0),
                }
