from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class ApiRequestLogRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema='platform' AND table_name='api_request_log' LIMIT 1
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def record(
        self,
        org_id: str,
        *,
        api_key_id: str | None = None,
        method: str | None = None,
        path: str | None = None,
        status_code: int | None = None,
        scope_used: list[str] | None = None,
        idempotency_key: str | None = None,
        ip_address: str | None = None,
    ) -> dict:
        row_id = str(uuid4())
        if not self.schema_ready():
            return {"id": row_id, "status": "schema_not_ready"}
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO platform.api_request_log (
                        id, org_id, api_key_id, method, path, status_code,
                        scope_used, idempotency_key, ip_address
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s::uuid, %s, %s, %s,
                        %s::jsonb, %s, %s::inet
                    )
                    RETURNING id::text
                    """,
                    (
                        row_id,
                        org_id,
                        api_key_id,
                        method,
                        path,
                        status_code,
                        Json(scope_used or []),
                        idempotency_key,
                        ip_address,
                    ),
                )
                conn.commit()
                return {"id": cur.fetchone()[0]}


api_request_log_repository = ApiRequestLogRepository()
