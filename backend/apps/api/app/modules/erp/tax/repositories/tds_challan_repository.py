from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class TdsChallanRepository:
    def create(self, org_id: str, **fields) -> dict:
        cid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.tds_challans (
                      id, org_id, tax_type, challan_no, bsr_code, cin, deposit_date,
                      amount, quarter, financial_year, status, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s,%s,%s,%s,%s::date,%s,%s,%s,%s,%s::jsonb)
                    RETURNING id::text, challan_no, amount, status, tax_type
                    """,
                    (
                        cid,
                        org_id,
                        fields.get("tax_type", "TDS"),
                        fields.get("challan_no"),
                        fields.get("bsr_code"),
                        fields.get("cin"),
                        fields.get("deposit_date"),
                        fields.get("amount", 0),
                        fields.get("quarter"),
                        fields.get("financial_year"),
                        fields.get("status", "pending"),
                        Json(fields.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": cid})

    def get(self, org_id: str, *, challan_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, tax_type, challan_no, bsr_code, cin, deposit_date::text,
                           amount, quarter, financial_year, status
                    FROM erp.tds_challans
                    WHERE org_id=%s::uuid AND id=%s::uuid
                    """,
                    (org_id, challan_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(self, org_id: str, *, status: str | None = None, limit: int = 200) -> list[dict]:
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if status:
            where.append("status = %s")
            params.append(status)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, tax_type, challan_no, bsr_code, cin, deposit_date::text,
                           amount, quarter, financial_year, status
                    FROM erp.tds_challans
                    WHERE {' AND '.join(where)}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def set_status(self, org_id: str, *, challan_id: str, status: str, **fields) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.tds_challans
                    SET status=%s, challan_no=COALESCE(%s, challan_no), bsr_code=COALESCE(%s, bsr_code),
                        cin=COALESCE(%s, cin), deposit_date=COALESCE(%s::date, deposit_date),
                        updated_at=NOW()
                    WHERE org_id=%s::uuid AND id=%s::uuid
                    RETURNING id::text, status, challan_no, amount
                    """,
                    (
                        status,
                        fields.get("challan_no"),
                        fields.get("bsr_code"),
                        fields.get("cin"),
                        fields.get("deposit_date"),
                        org_id,
                        challan_id,
                    ),
                )
                row = cur.fetchone()
                return dict(row) if row else {"id": challan_id, "status": status}


tds_challan_repository = TdsChallanRepository()
