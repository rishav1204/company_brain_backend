from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class MatchRepository:
    def create(
        self,
        org_id: str,
        *,
        po_id: str,
        grn_id: str | None = None,
        ap_invoice_id: str | None = None,
        match_score: float = 0,
        match_status: str = "pending",
        variance_json: dict | None = None,
    ) -> dict:
        mid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.procurement_matches (
                      id, org_id, po_id, grn_id, ap_invoice_id, match_score, match_status, variance_json
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::numeric,%s,%s::jsonb)
                    RETURNING id::text, match_status, match_score
                    """,
                    (
                        mid, org_id, po_id, grn_id, ap_invoice_id,
                        match_score, match_status, Json(variance_json or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": mid})

    def get(self, org_id: str, *, match_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, po_id::text, grn_id::text, ap_invoice_id::text,
                           match_score, match_status, variance_json, override_by::text,
                           override_reason, workflow_approved, created_at::text
                    FROM erp.procurement_matches
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, match_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def get_for_invoice(self, org_id: str, *, ap_invoice_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, po_id::text, grn_id::text, ap_invoice_id::text,
                           match_score, match_status, variance_json, workflow_approved
                    FROM erp.procurement_matches
                    WHERE org_id = %s::uuid AND ap_invoice_id = %s::uuid
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (org_id, ap_invoice_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(self, org_id: str, *, po_id: str | None = None, limit: int = 100) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if po_id:
                    cur.execute(
                        """
                        SELECT id::text, po_id::text, grn_id::text, ap_invoice_id::text,
                               match_status, match_score, created_at::text
                        FROM erp.procurement_matches
                        WHERE org_id = %s::uuid AND po_id = %s::uuid
                        ORDER BY created_at DESC LIMIT %s
                        """,
                        (org_id, po_id, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, po_id::text, grn_id::text, ap_invoice_id::text,
                               match_status, match_score, created_at::text
                        FROM erp.procurement_matches
                        WHERE org_id = %s::uuid
                        ORDER BY created_at DESC LIMIT %s
                        """,
                        (org_id, limit),
                    )
                return [dict(r) for r in cur.fetchall()]

    def update_match(
        self,
        org_id: str,
        *,
        match_id: str,
        match_status: str,
        match_score: float,
        variance_json: dict,
        ap_invoice_id: str | None = None,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.procurement_matches
                    SET match_status = %s, match_score = %s::numeric, variance_json = %s::jsonb,
                        ap_invoice_id = COALESCE(%s::uuid, ap_invoice_id), updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, match_status, match_score
                    """,
                    (match_status, match_score, Json(variance_json), ap_invoice_id, org_id, match_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {}

    def override(
        self,
        org_id: str,
        *,
        match_id: str,
        override_by: str,
        override_reason: str,
        workflow_approved: bool = True,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.procurement_matches
                    SET match_status = 'matched_within_tolerance',
                        override_by = %s::uuid, override_reason = %s,
                        workflow_approved = %s, updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, match_status, override_reason
                    """,
                    (override_by, override_reason, workflow_approved, org_id, match_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {}


match_repository = MatchRepository()
