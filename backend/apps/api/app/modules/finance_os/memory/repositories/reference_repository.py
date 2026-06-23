from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class ReferenceRepository:
    def create_batch(self, org_id: str, *, memory_id: str, references: list[dict]) -> None:
        if not references:
            return
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                for ref in references:
                    cur.execute(
                        """
                        INSERT INTO finance_os.memory_references (id, org_id, memory_id, source_type, source_id)
                        VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s::uuid)
                        """,
                        (
                            str(uuid4()),
                            org_id,
                            memory_id,
                            ref.get("source_type", "unknown"),
                            ref.get("source_id"),
                        ),
                    )

    def list_for_memory(self, org_id: str, memory_id: str, limit: int = 500) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, source_type, source_id::text AS source_id, created_at::text
                    FROM finance_os.memory_references
                    WHERE org_id = %s::uuid AND memory_id = %s::uuid
                    LIMIT %s

                    """,
                    (org_id, memory_id),
                )
                return [dict(r) for r in cur.fetchall()]


reference_repository = ReferenceRepository()
