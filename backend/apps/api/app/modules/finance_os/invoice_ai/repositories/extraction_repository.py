from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class ExtractionRepository:
    def create(self, org_id: str, *, data: dict) -> dict:
        extraction_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_os.invoice_extractions (
                        id, org_id, document_id, source_extraction_id, invoice_number,
                        vendor_name, vendor_name_normalized, vendor_gstin, vendor_id,
                        invoice_date, due_date, taxable_amount, gst_amount, total_amount,
                        extraction_confidence, confidence_band, invoice_type, metadata
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s::uuid,
                        %s::date, %s::date, %s, %s, %s, %s, %s, %s, %s::jsonb
                    )
                    RETURNING id::text, document_id::text AS document_id, invoice_number,
                              vendor_name, vendor_gstin, total_amount::float8 AS total_amount,
                              extraction_confidence::float8 AS extraction_confidence,
                              confidence_band, invoice_type, created_at::text
                    """,
                    (
                        extraction_id,
                        org_id,
                        data["document_id"],
                        data.get("source_extraction_id"),
                        data.get("invoice_number"),
                        data.get("vendor_name"),
                        data.get("vendor_name_normalized"),
                        data.get("vendor_gstin"),
                        data.get("vendor_id"),
                        data.get("invoice_date"),
                        data.get("due_date"),
                        data.get("taxable_amount", 0),
                        data.get("gst_amount", 0),
                        data.get("total_amount", 0),
                        data.get("extraction_confidence", 0),
                        data.get("confidence_band", "manual_review"),
                        data.get("invoice_type", "purchase"),
                        Json(data.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {})

    def get(self, org_id: str, extraction_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, document_id::text AS document_id, source_extraction_id::text,
                           invoice_number, vendor_name, vendor_name_normalized, vendor_gstin,
                           vendor_id::text AS vendor_id, invoice_date::text AS invoice_date,
                           due_date::text AS due_date, taxable_amount::float8 AS taxable_amount,
                           gst_amount::float8 AS gst_amount, total_amount::float8 AS total_amount,
                           extraction_confidence::float8 AS extraction_confidence,
                           confidence_band, invoice_type, metadata, created_at::text
                    FROM finance_os.invoice_extractions
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, extraction_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list_review_queue(self, org_id: str, *, limit: int = 50) -> list[dict]:
        """Extractions needing human review: non auto-suggest band, suspected duplicate, or open anomaly."""
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.id::text AS id,
                           e.id::text AS extraction_id,
                           e.document_id::text AS document_id,
                           e.invoice_number,
                           e.vendor_name,
                           e.total_amount::float8 AS total_amount,
                           e.extraction_confidence::float8 AS overall_score,
                           e.confidence_band,
                           e.created_at::text AS created_at,
                           d.matched_invoice_id::text AS duplicate_of,
                           d.status AS duplicate_status,
                           a.max_score AS anomaly_score,
                           a.top_severity AS anomaly_severity
                    FROM finance_os.invoice_extractions e
                    LEFT JOIN LATERAL (
                        SELECT ds.matched_invoice_id, ds.status
                        FROM finance_os.invoice_duplicate_scores ds
                        WHERE ds.org_id = e.org_id AND ds.extraction_id = e.id
                        ORDER BY ds.created_at DESC
                        LIMIT 1
                    ) d ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT MAX(an.anomaly_score)::float8 AS max_score,
                               (ARRAY_AGG(an.severity ORDER BY an.anomaly_score DESC))[1] AS top_severity
                        FROM finance_os.invoice_anomalies an
                        WHERE an.org_id = e.org_id AND an.extraction_id = e.id AND an.status = 'open'
                    ) a ON TRUE
                    WHERE e.org_id = %s::uuid
                      AND (
                        e.confidence_band <> 'auto_suggest'
                        OR d.status IN ('suspected', 'confirmed')
                        OR a.max_score IS NOT NULL
                      )
                    ORDER BY e.created_at DESC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]

    def latest_for_document(self, org_id: str, document_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, document_id::text AS document_id, invoice_number, vendor_name,
                           vendor_gstin, total_amount::float8 AS total_amount,
                           extraction_confidence::float8 AS extraction_confidence,
                           confidence_band, created_at::text
                    FROM finance_os.invoice_extractions
                    WHERE org_id = %s::uuid AND document_id = %s::uuid
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (org_id, document_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None
