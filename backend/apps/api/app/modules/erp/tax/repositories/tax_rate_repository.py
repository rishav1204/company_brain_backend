from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class TaxRateRepository:
    def list_active(self, org_id: str, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, hsn_sac, description, gst_rate, cess_rate
                    FROM erp.tax_rate_master
                    WHERE org_id=%s::uuid AND is_active=true
                    ORDER BY gst_rate
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def create(self, org_id: str, **fields) -> dict:
        rid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.tax_rate_master (id, org_id, hsn_sac, description, gst_rate, cess_rate, metadata)
                    VALUES (%s::uuid,%s::uuid,%s,%s,%s,%s,%s::jsonb)
                    RETURNING id::text, hsn_sac, gst_rate
                    """,
                    (
                        rid, org_id, fields.get("hsn_sac"), fields.get("description"),
                        fields["gst_rate"], fields.get("cess_rate", 0), Json(fields.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": rid})

    def resolve_rate(self, org_id: str, *, hsn_sac: str | None, fallback: float) -> float:
        rates = self.list_active(org_id)
        if hsn_sac:
            for row in rates:
                if str(row.get("hsn_sac") or "") == hsn_sac:
                    return float(row["gst_rate"])
        for row in rates:
            if row.get("hsn_sac") is None and float(row.get("gst_rate") or 0) == fallback:
                return fallback
        return fallback


tax_rate_repository = TaxRateRepository()
