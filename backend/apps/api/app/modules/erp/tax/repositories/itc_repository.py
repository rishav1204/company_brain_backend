from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class ItcLedgerRepository:
    def create(self, org_id: str, **fields) -> dict:
        iid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.itc_ledger (id, org_id, gst_transaction_id, itc_type, eligible_amount, claimed_amount, status, metadata)
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s,%s,%s,%s::jsonb)
                    RETURNING id::text, itc_type, eligible_amount, status
                    """,
                    (iid, org_id, fields["gst_transaction_id"], fields["itc_type"],
                     fields.get("eligible_amount", 0), fields.get("claimed_amount", 0),
                     fields.get("status", "eligible"), Json(fields.get("metadata") or {})),
                )
                return dict(cur.fetchone() or {"id": iid})

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
                    f"SELECT id::text, gst_transaction_id::text, itc_type, eligible_amount, claimed_amount, status FROM erp.itc_ledger WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT %s",
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def claim(self, org_id: str, *, itc_id: str, claimed_amount: float) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.itc_ledger SET claimed_amount = %s, status = 'claimed', updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, claimed_amount, status
                    """,
                    (claimed_amount, org_id, itc_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("ITC entry not found")
                return dict(row)

    def sum_claimed(self, org_id: str, *, return_period: str | None = None) -> float:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if return_period:
                    cur.execute(
                        """
                        SELECT COALESCE(SUM(i.claimed_amount),0) AS total
                        FROM erp.itc_ledger i
                        JOIN erp.gst_transactions g ON g.id = i.gst_transaction_id
                        WHERE i.org_id=%s::uuid AND g.return_period=%s
                        """,
                        (org_id, return_period),
                    )
                else:
                    cur.execute(
                        "SELECT COALESCE(SUM(claimed_amount),0) AS total FROM erp.itc_ledger WHERE org_id=%s::uuid",
                        (org_id,),
                    )
                return float((cur.fetchone() or {}).get("total") or 0)

    def summary_by_period(self, org_id: str, *, return_period: str | None = None) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if return_period:
                    cur.execute(
                        """
                        SELECT COALESCE(SUM(i.eligible_amount),0) AS eligible,
                               COALESCE(SUM(i.claimed_amount),0) AS claimed
                        FROM erp.itc_ledger i
                        JOIN erp.gst_transactions g ON g.id = i.gst_transaction_id
                        WHERE i.org_id=%s::uuid AND g.return_period=%s
                        """,
                        (org_id, return_period),
                    )
                else:
                    cur.execute(
                        "SELECT COALESCE(SUM(eligible_amount),0) AS eligible, COALESCE(SUM(claimed_amount),0) AS claimed FROM erp.itc_ledger WHERE org_id=%s::uuid",
                        (org_id,),
                    )
                row = dict(cur.fetchone() or {})
                eligible = float(row.get("eligible") or 0)
                claimed = float(row.get("claimed") or 0)
                return {"eligible_total": round(eligible, 2), "claimed_total": round(claimed, 2), "available": round(eligible - claimed, 2), "return_period": return_period}


class ItcBlockedRulesRepository:
    def list_active(self, org_id: str, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id::text, category, description, block_percentage FROM erp.itc_blocked_rules WHERE org_id=%s::uuid AND is_active=true LIMIT %s",
                    (org_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def list_all(self, org_id: str, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id::text, category, description, block_percentage, is_active FROM erp.itc_blocked_rules WHERE org_id=%s::uuid ORDER BY category LIMIT %s",
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
                    INSERT INTO erp.itc_blocked_rules (id, org_id, category, description, block_percentage, is_active, metadata)
                    VALUES (%s::uuid,%s::uuid,%s,%s,%s,%s,%s::jsonb)
                    RETURNING id::text, category, block_percentage, is_active
                    """,
                    (rid, org_id, fields["category"], fields.get("description"), fields.get("block_percentage", 100), fields.get("is_active", True), Json(fields.get("metadata") or {})),
                )
                return dict(cur.fetchone() or {"id": rid})

    def update(self, org_id: str, *, rule_id: str, **fields) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.itc_blocked_rules
                    SET category=COALESCE(%s, category), description=COALESCE(%s, description),
                        block_percentage=COALESCE(%s, block_percentage), is_active=COALESCE(%s, is_active)
                    WHERE org_id=%s::uuid AND id=%s::uuid
                    RETURNING id::text, category, block_percentage, is_active
                    """,
                    (fields.get("category"), fields.get("description"), fields.get("block_percentage"), fields.get("is_active"), org_id, rule_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("ITC blocked rule not found")
                return dict(row)


itc_ledger_repository = ItcLedgerRepository()
itc_blocked_rules_repository = ItcBlockedRulesRepository()
