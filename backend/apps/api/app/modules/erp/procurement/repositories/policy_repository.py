from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class PolicyRepository:
    def get_active(self, org_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, policy_name, mandatory_po, mandatory_quotations,
                           preferred_vendors_only, budget_enforcement, approval_thresholds,
                           qty_tolerance_pct, price_tolerance_pct, amount_tolerance_pct, metadata
                    FROM erp.procurement_policies
                    WHERE org_id = %s::uuid AND is_active = true
                    ORDER BY created_at LIMIT 1
                    """,
                    (org_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, policy_name, mandatory_po, budget_enforcement, is_active,
                           price_tolerance_pct, amount_tolerance_pct
                    FROM erp.procurement_policies
                    WHERE org_id = %s::uuid
                    ORDER BY policy_name
                    """,
                    (org_id,),
                )
                return [dict(r) for r in cur.fetchall()]

    def upsert_default(self, org_id: str, *, policy: dict) -> dict:
        pid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.procurement_policies (
                      id, org_id, policy_name, mandatory_po, mandatory_quotations,
                      preferred_vendors_only, budget_enforcement, approval_thresholds,
                      qty_tolerance_pct, price_tolerance_pct, amount_tolerance_pct
                    )
                    VALUES (%s::uuid,%s::uuid,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
                    ON CONFLICT DO NOTHING
                    RETURNING id::text, policy_name
                    """,
                    (
                        pid, org_id,
                        policy.get("policy_name", "default"),
                        policy.get("mandatory_po", True),
                        policy.get("mandatory_quotations", 0),
                        policy.get("preferred_vendors_only", False),
                        policy.get("budget_enforcement", False),
                        Json(policy.get("approval_thresholds") or []),
                        policy.get("qty_tolerance_pct", 0),
                        policy.get("price_tolerance_pct", 2),
                        policy.get("amount_tolerance_pct", 2),
                    ),
                )
                row = cur.fetchone()
                return dict(row) if row else {}


class BudgetEnvelopeRepository:
    def get_for_cost_center(
        self,
        org_id: str,
        *,
        cost_center_id: str,
        fiscal_year_id: str | None = None,
    ) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, cost_center_id::text, fiscal_year_id::text,
                           allocated, committed, consumed
                    FROM erp.budget_envelopes
                    WHERE org_id = %s::uuid AND cost_center_id = %s::uuid
                      AND (fiscal_year_id IS NOT DISTINCT FROM %s::uuid)
                    LIMIT 1
                    """,
                    (org_id, cost_center_id, fiscal_year_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def commit(self, org_id: str, *, envelope_id: str, amount: float) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.budget_envelopes
                    SET committed = committed + %s::numeric, updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, allocated, committed, consumed
                    """,
                    (amount, org_id, envelope_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {}

    def release(self, org_id: str, *, envelope_id: str, amount: float) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.budget_envelopes
                    SET committed = GREATEST(0, committed - %s::numeric), updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, allocated, committed, consumed
                    """,
                    (amount, org_id, envelope_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {}

    def consume(self, org_id: str, *, envelope_id: str, amount: float) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.budget_envelopes
                    SET consumed = consumed + %s::numeric,
                        committed = GREATEST(0, committed - %s::numeric),
                        updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, allocated, committed, consumed
                    """,
                    (amount, amount, org_id, envelope_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {}


policy_repository = PolicyRepository()
budget_envelope_repository = BudgetEnvelopeRepository()
