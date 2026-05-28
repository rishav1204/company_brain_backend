from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class QueueRepository:
    def create_job(
        self,
        *,
        org_id: str,
        queue_name: str,
        job_type: str,
        payload: dict,
        event_id: str | None = None,
        max_retries: int = 5,
    ) -> dict[str, Any]:
        job_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO platform.queue_jobs (
                        id, org_id, queue_name, event_id, job_type, payload, max_retries
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s::uuid, %s, %s::jsonb, %s)
                    RETURNING id::text AS id, status, created_at
                    """,
                    (job_id, org_id, queue_name, event_id, job_type, Json(payload), max_retries),
                )
                return cur.fetchone() or {"id": job_id}

    def update_job_status(
        self,
        org_id: str,
        job_id: str,
        *,
        status: str,
        attempt_count: int | None = None,
        error_detail: str | None = None,
    ) -> None:
        sets = ["status = %s"]
        params: list[Any] = [status]
        if attempt_count is not None:
            sets.append("attempt_count = %s")
            params.append(attempt_count)
        if error_detail is not None:
            sets.append("error_detail = %s")
            params.append(error_detail)
        if status == "processing":
            sets.append("started_at = NOW()")
        if status in {"completed", "failed", "dlq"}:
            sets.append("completed_at = NOW()")
        params.extend([job_id, org_id])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE platform.queue_jobs SET {', '.join(sets)} WHERE id = %s::uuid AND org_id = %s::uuid",
                    tuple(params),
                )

    def list_jobs(self, org_id: str, *, queue_name: str | None = None, status: str | None = None, limit: int = 50) -> list[dict]:
        clauses = ["org_id = %s::uuid"]
        params: list[Any] = [org_id]
        if queue_name:
            clauses.append("queue_name = %s")
            params.append(queue_name)
        if status:
            clauses.append("status = %s")
            params.append(status)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text AS id, queue_name, job_type, status, attempt_count, max_retries, created_at
                    FROM platform.queue_jobs
                    WHERE {' AND '.join(clauses)}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return cur.fetchall() or []


queue_repository = QueueRepository()
