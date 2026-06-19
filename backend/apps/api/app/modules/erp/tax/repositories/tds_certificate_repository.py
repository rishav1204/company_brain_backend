from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class TdsCertificateRepository:
    def get(self, org_id: str, *, vendor_id: str, quarter: str, financial_year: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, vendor_id::text, quarter, financial_year, document_id::text, payload
                    FROM erp.tds_certificates
                    WHERE org_id=%s::uuid AND vendor_id=%s::uuid AND quarter=%s AND financial_year=%s
                    """,
                    (org_id, vendor_id, quarter, financial_year),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def upsert(self, org_id: str, *, vendor_id: str, quarter: str, financial_year: str, document_id: str | None, payload: dict) -> dict:
        cid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.tds_certificates (id, org_id, vendor_id, quarter, financial_year, document_id, payload)
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s,%s::uuid,%s::jsonb)
                    ON CONFLICT (org_id, vendor_id, quarter, financial_year) DO UPDATE
                      SET document_id=EXCLUDED.document_id, payload=EXCLUDED.payload
                    RETURNING id::text, document_id::text
                    """,
                    (cid, org_id, vendor_id, quarter, financial_year, document_id, Json(payload)),
                )
                return dict(cur.fetchone() or {"id": cid})


tds_certificate_repository = TdsCertificateRepository()
