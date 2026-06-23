from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class ExtractionRepository:
    def create_extraction(
        self,
        org_id: str,
        *,
        document_id: str,
        extraction_type: str,
        extracted_data: dict,
        confidence_score: float,
        extraction_status: str,
    ) -> dict:
        extraction_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents.extractions (
                        id, org_id, document_id, extraction_type, extracted_data, confidence_score,
                        extraction_status, processed_at
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s::jsonb, %s, %s, NOW())
                    RETURNING id::text, document_id::text AS document_id, extraction_type, extracted_data,
                              confidence_score::float8 AS confidence_score, extraction_status, processed_at::text
                    """,
                    (
                        extraction_id,
                        org_id,
                        document_id,
                        extraction_type,
                        Json(extracted_data),
                        confidence_score,
                        extraction_status,
                    ),
                )
                return dict(cur.fetchone() or {})

    def latest_extraction(self, org_id: str, document_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, document_id::text AS document_id, extraction_type, extracted_data,
                           confidence_score::float8 AS confidence_score, extraction_status, processed_at::text
                    FROM documents.extractions
                    WHERE org_id = %s::uuid AND document_id = %s::uuid
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (org_id, document_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def get_extraction(self, org_id: str, *, extraction_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, org_id::text AS org_id, document_id::text AS document_id,
                           extraction_type, extracted_data, confidence_score::float8 AS confidence_score,
                           extraction_status, processed_at::text, created_at::text
                    FROM documents.extractions
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, extraction_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def latest_embedding_text(self, org_id: str, document_id: str) -> str | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT embedding::text AS embedding_text
                    FROM documents.semantic_embeddings
                    WHERE org_id = %s::uuid AND document_id = %s::uuid AND embedding IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (org_id, document_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return str(row.get("embedding_text") or "").strip() or None

    def create_classification(
        self,
        org_id: str,
        *,
        document_id: str,
        classification: str,
        confidence_score: float,
        classified_by: str = "system",
    ) -> dict:
        classification_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents.classifications (
                        id, org_id, document_id, classification, confidence_score, classified_by
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s)
                    RETURNING id::text, document_id::text AS document_id, classification,
                              confidence_score::float8 AS confidence_score, classified_by, created_at::text
                    """,
                    (classification_id, org_id, document_id, classification, confidence_score, classified_by),
                )
                return dict(cur.fetchone() or {})

    def add_embedding(self, org_id: str, *, document_id: str, embedding: list[float], metadata: dict | None = None) -> dict:
        embedding_id = str(uuid4())
        vector_literal = "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents.semantic_embeddings (id, org_id, document_id, embedding, metadata)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::vector, %s::jsonb)
                    RETURNING id::text, document_id::text AS document_id, created_at::text
                    """,
                    (embedding_id, org_id, document_id, vector_literal, Json(metadata or {})),
                )
                return dict(cur.fetchone() or {})

    def add_chunk_embedding(
        self,
        org_id: str,
        *,
        document_id: str,
        content: str,
        embedding: list[float] | None,
        page_number: int | None,
        chunk_index: int,
        metadata: dict | None = None,
    ) -> dict:
        chunk_id = str(uuid4())
        vector_literal = None
        if embedding is not None:
            vector_literal = "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents.semantic_chunks (
                        id, org_id, document_id, page_number, chunk_index, content, embedding, metadata
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::vector, %s::jsonb
                    )
                    RETURNING id::text, document_id::text AS document_id, created_at::text
                    """,
                    (
                        chunk_id,
                        org_id,
                        document_id,
                        page_number,
                        chunk_index,
                        content,
                        vector_literal,
                        Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {})

    def search_chunk_embeddings(
        self,
        org_id: str,
        *,
        query_embedding: list[float],
        top_k: int = 20,
        document_type: str | None = None,
        keyword: str | None = None,
        limit: int = 500,
    ) -> list[dict]:
        top_k = max(1, min(int(top_k or 20), 50))
        vector_literal = "[" + ",".join(f"{v:.8f}" for v in query_embedding) + "]"
        base = """
            SELECT
                sc.document_id::text AS document_id,
                sc.page_number::int AS page_number,
                sc.chunk_index::int AS chunk_index,
                (sc.embedding <=> %s::vector) AS distance,
                left(sc.content, 800) AS snippet,
                d.document_type,
                d.file_name,
                d.mime_type,
                d.storage_path,
                d.status,
                sc.metadata
            FROM documents.semantic_chunks sc
            JOIN documents.documents d ON d.id = sc.document_id
            WHERE sc.org_id = %s::uuid
              AND sc.embedding IS NOT NULL
        """
        params: list[object] = [vector_literal, org_id]
        if document_type:
            base += " AND d.document_type = %s"
            params.append(document_type)
        if keyword:
            base += " AND to_tsvector('simple', sc.content) @@ plainto_tsquery('simple', %s)"
            params.append(keyword)
        base += " ORDER BY sc.embedding <=> %s::vector LIMIT %s"
        params.extend([vector_literal, top_k])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(base, tuple(params))
                return [dict(r) for r in cur.fetchall()]

    def search_embeddings(
        self,
        org_id: str,
        *,
        query_embedding: list[float],
        top_k: int = 20,
        document_type: str | None = None,
        limit: int = 500,
    ) -> list[dict]:
        top_k = max(1, min(int(top_k or 20), 50))
        vector_literal = "[" + ",".join(f"{v:.8f}" for v in query_embedding) + "]"
        base = """
            SELECT
                se.document_id::text AS document_id,
                (se.embedding <=> %s::vector) AS distance,
                d.document_type,
                d.file_name,
                d.mime_type,
                d.storage_path,
                d.checksum_hash,
                d.status,
                d.file_size::int AS file_size,
                d.created_at::text AS created_at,
                se.metadata
            FROM documents.semantic_embeddings se
            JOIN documents.documents d ON d.id = se.document_id
            WHERE se.org_id = %s::uuid
        """
        params: list[object] = [vector_literal, org_id]
        if document_type:
            base += " AND d.document_type = %s"
            params.append(document_type)
        base += " ORDER BY se.embedding <=> %s::vector LIMIT %s"
        params.extend([vector_literal, top_k])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(base, tuple(params))
                return [dict(r) for r in cur.fetchall()]


extraction_repository = ExtractionRepository()
