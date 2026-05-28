from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class DocumentRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'documents' AND table_name = 'documents'
                        LIMIT 1
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def create_document(
        self,
        org_id: str,
        *,
        document_type: str,
        file_name: str,
        mime_type: str,
        storage_path: str,
        checksum_hash: str,
        uploaded_by: str | None,
        file_size: int,
        metadata: dict | None = None,
        malware_scan_status: str = "pending",
        retention_until: str | None = None,
    ) -> dict:
        doc_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents.documents (
                        id, org_id, document_type, file_name, mime_type, storage_path,
                        checksum_hash, uploaded_by, status, file_size, metadata, malware_scan_status, retention_until,
                        original_storage_path, current_storage_path, current_version_number
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s::uuid, 'uploaded', %s, %s::jsonb, %s, %s::timestamptz,
                            %s, %s, 1)
                    RETURNING id::text, document_type, file_name, mime_type, storage_path, checksum_hash,
                              status, file_size, created_at::text
                    """,
                    (
                        doc_id,
                        org_id,
                        document_type,
                        file_name,
                        mime_type,
                        storage_path,
                        checksum_hash,
                        uploaded_by,
                        file_size,
                        Json(metadata or {}),
                        malware_scan_status,
                        retention_until,
                        storage_path,
                        storage_path,
                    ),
                )
                return dict(cur.fetchone() or {})

    def get_document(self, org_id: str, document_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, document_type, file_name, mime_type, storage_path, checksum_hash,
                           status, file_size, metadata, created_at::text
                    FROM documents.documents
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, document_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list_documents(self, org_id: str, *, limit: int = 50, document_type: str | None = None) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if document_type:
                    cur.execute(
                        """
                        SELECT id::text, document_type, file_name, mime_type, storage_path, checksum_hash,
                               status, file_size, metadata, created_at::text
                        FROM documents.documents
                        WHERE org_id = %s::uuid AND document_type = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (org_id, document_type, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, document_type, file_name, mime_type, storage_path, checksum_hash,
                               status, file_size, metadata, created_at::text
                        FROM documents.documents
                        WHERE org_id = %s::uuid
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (org_id, limit),
                    )
                return [dict(r) for r in cur.fetchall()]

    def set_malware_scan_result(
        self,
        org_id: str,
        *,
        document_id: str,
        status: str,
        provider: str,
        detail: str | None = None,
    ) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE documents.documents
                    SET malware_scan_status = %s,
                        malware_scan_provider = %s,
                        malware_scan_detail = %s,
                        malware_scanned_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (status, provider, detail, org_id, document_id),
                )

    def update_status(self, org_id: str, *, document_id: str, status: str) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE documents.documents
                    SET status = %s
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (status, org_id, document_id),
                )

    def set_current_version(self, org_id: str, *, document_id: str, storage_path: str, version_number: int) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE documents.documents
                    SET current_storage_path = %s,
                        storage_path = %s,
                        current_version_number = %s
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (storage_path, storage_path, int(version_number), org_id, document_id),
                )

    def list_retention_expired(self, org_id: str, *, limit: int = 200) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, file_name, document_type, retention_until::text AS retention_until, status
                    FROM documents.documents
                    WHERE org_id = %s::uuid
                      AND retention_until IS NOT NULL
                      AND retention_until < NOW()
                      AND status NOT IN ('expired', 'deleted')
                    ORDER BY retention_until ASC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]

    def create_version(
        self,
        org_id: str,
        *,
        document_id: str,
        storage_path: str,
        uploaded_by: str | None,
        change_reason: str,
        metadata: dict | None = None,
    ) -> dict:
        version_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version
                    FROM documents.document_versions
                    WHERE org_id = %s::uuid AND document_id = %s::uuid
                    """,
                    (org_id, document_id),
                )
                next_version = int((cur.fetchone() or {}).get("next_version") or 1)
                cur.execute(
                    """
                    INSERT INTO documents.document_versions (
                        id, org_id, document_id, version_number, storage_path, uploaded_by, change_reason, metadata
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s::uuid, %s, %s::jsonb)
                    RETURNING id::text, document_id::text AS document_id, version_number, storage_path, created_at::text
                    """,
                    (version_id, org_id, document_id, next_version, storage_path, uploaded_by, change_reason, Json(metadata or {})),
                )
                return dict(cur.fetchone() or {})


document_repository = DocumentRepository()
