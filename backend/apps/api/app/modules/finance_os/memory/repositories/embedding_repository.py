from __future__ import annotations

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class EmbeddingRepository:
    def create(self, org_id: str, *, memory_id: str, embedding: list[float]) -> dict:
        emb_id = str(uuid4())
        vec = f"[{','.join(str(x) for x in embedding)}]"
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_os.memory_embeddings (id, org_id, memory_id, embedding)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::vector)
                    RETURNING id::text, memory_id::text AS memory_id
                    """,
                    (emb_id, org_id, memory_id, vec),
                )
                return dict(cur.fetchone() or {})

    def search(self, org_id: str, *, query_embedding: list[float], top_k: int = 10, memory_type: str | None = None) -> list[dict]:
        vec = f"[{','.join(str(x) for x in query_embedding)}]"
        type_filter = ""
        params: list = [vec, org_id]
        if memory_type:
            type_filter = " AND e.memory_type = %s"
            params.append(memory_type)
        params.extend([vec, top_k])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT e.id::text, e.memory_type, e.entity_type, e.entity_id::text AS entity_id,
                           e.title, e.content, e.importance_score::float8 AS importance_score,
                           (emb.embedding <=> %s::vector)::float8 AS distance
                    FROM finance_os.memory_embeddings emb
                    JOIN finance_os.memory_entries e ON e.id = emb.memory_id AND e.org_id = emb.org_id
                    WHERE emb.org_id = %s::uuid AND e.status = 'active'{type_filter}
                    ORDER BY emb.embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (vec, org_id, *([memory_type] if memory_type else []), vec, top_k),
                )
                return [dict(r) for r in cur.fetchall()]


embedding_repository = EmbeddingRepository()
