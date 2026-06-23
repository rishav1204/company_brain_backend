from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from app.services.db import get_db_conn, set_rls_org


class TdsRuleRepository:
    def list(self, org_id: str, limit: int = 500) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT section_code, threshold_amount, rate_pan, rate_no_pan,
                           applicable_entity, payment_type, expense_category, pan_required
                    FROM erp.tds_rules
                    WHERE org_id=%s::uuid AND is_active=true
                    ORDER BY section_code
                    LIMIT %s
                    """,
                    (org_id,),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def resolve(
        self,
        org_id: str,
        *,
        payment_type: str | None = None,
        expense_category: str | None = None,
        applicable_entity: str = "vendor",
    ) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if payment_type:
                    cur.execute(
                        """
                        SELECT section_code, threshold_amount, rate_pan, rate_no_pan, pan_required
                        FROM erp.tds_rules
                        WHERE org_id=%s::uuid AND is_active=true
                          AND applicable_entity=%s AND payment_type=%s
                        LIMIT 1
                        """,
                        (org_id, applicable_entity, payment_type.lower()),
                    )
                    row = cur.fetchone()
                    if row:
                        return dict(row)
                if expense_category:
                    cur.execute(
                        """
                        SELECT section_code, threshold_amount, rate_pan, rate_no_pan, pan_required
                        FROM erp.tds_rules
                        WHERE org_id=%s::uuid AND is_active=true
                          AND applicable_entity=%s AND expense_category=%s
                        LIMIT 1
                        """,
                        (org_id, applicable_entity, expense_category.lower()),
                    )
                    row = cur.fetchone()
                    if row:
                        return dict(row)
        return None


tds_rule_repository = TdsRuleRepository()
