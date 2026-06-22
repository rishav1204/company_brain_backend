from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class BillingRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'billing' AND table_name = 'plans'
                        LIMIT 1
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def list_plans(self) -> list[dict[str, Any]]:
        if not self.schema_ready():
            return []
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT plan_key, name, tier, monthly_price_inr, included_ai_credits, status
                    FROM billing.plans ORDER BY tier ASC
                    """
                )
                return [dict(row) for row in cur.fetchall()]

    def get_plan_features(self, plan_key: str) -> list[str]:
        if not self.schema_ready():
            return []
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT feature_code FROM billing.plan_features
                    WHERE plan_key = %s AND enabled = TRUE
                    """,
                    (plan_key,),
                )
                return [row["feature_code"] for row in cur.fetchall()]

    def get_plan_limits(self, plan_key: str) -> dict[str, int | None]:
        if not self.schema_ready():
            return {}
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT limit_code, limit_value FROM billing.plan_limits WHERE plan_key = %s
                    """,
                    (plan_key,),
                )
                return {row["limit_code"]: row["limit_value"] for row in cur.fetchall()}

    def get_org_subscription(self, org_id: str) -> dict[str, Any] | None:
        if not self.schema_ready():
            return None
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, org_id::text, plan_key, status, started_at, renews_at, trial_ends_at
                    FROM billing.org_subscriptions WHERE org_id = %s::uuid
                    """,
                    (org_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def upsert_org_subscription(
        self,
        org_id: str,
        *,
        plan_key: str,
        status: str = "active",
    ) -> dict[str, Any]:
        sub_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO billing.org_subscriptions (id, org_id, plan_key, status)
                    VALUES (%s::uuid, %s::uuid, %s, %s)
                    ON CONFLICT (org_id) DO UPDATE SET
                        plan_key = EXCLUDED.plan_key,
                        status = EXCLUDED.status,
                        updated_at = NOW()
                    RETURNING id::text, org_id::text, plan_key, status, started_at
                    """,
                    (sub_id, org_id, plan_key, status),
                )
                row = dict(cur.fetchone() or {})
                cur.execute(
                    "UPDATE core.organizations SET plan = %s WHERE id = %s::uuid",
                    (plan_key, org_id),
                )
                conn.commit()
                return row

    def list_org_entitlement_overrides(self, org_id: str) -> list[dict[str, Any]]:
        if not self.schema_ready():
            return []
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT feature_code, enabled, expires_at
                    FROM billing.org_entitlements
                    WHERE org_id = %s::uuid
                      AND (expires_at IS NULL OR expires_at > NOW())
                    """,
                    (org_id,),
                )
                return [dict(row) for row in cur.fetchall()]

    def upsert_org_entitlement(
        self,
        org_id: str,
        *,
        feature_code: str,
        enabled: bool,
        expires_at=None,
    ) -> dict[str, Any]:
        ent_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO billing.org_entitlements (id, org_id, feature_code, enabled, expires_at)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s)
                    ON CONFLICT (org_id, feature_code) DO UPDATE SET
                        enabled = EXCLUDED.enabled,
                        expires_at = EXCLUDED.expires_at
                    RETURNING feature_code, enabled, expires_at
                    """,
                    (ent_id, org_id, feature_code, enabled, expires_at),
                )
                conn.commit()
                return dict(cur.fetchone() or {})

    def get_credit_wallet(self, org_id: str) -> dict[str, Any] | None:
        if not self.schema_ready():
            return None
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, org_id::text, balance, included_monthly, purchased_balance, period_start
                    FROM billing.org_credit_wallets WHERE org_id = %s::uuid
                    """,
                    (org_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def ensure_credit_wallet(
        self,
        org_id: str,
        *,
        included_monthly: float = 0,
    ) -> dict[str, Any]:
        wallet_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO billing.org_credit_wallets (id, org_id, balance, included_monthly)
                    VALUES (%s::uuid, %s::uuid, %s, %s)
                    ON CONFLICT (org_id) DO NOTHING
                    RETURNING id::text, balance, included_monthly, purchased_balance, period_start
                    """,
                    (wallet_id, org_id, included_monthly, included_monthly),
                )
                row = cur.fetchone()
                if row:
                    conn.commit()
                    return dict(row)
                cur.execute(
                    """
                    SELECT id::text, balance, included_monthly, purchased_balance, period_start
                    FROM billing.org_credit_wallets WHERE org_id = %s::uuid
                    """,
                    (org_id,),
                )
                conn.commit()
                return dict(cur.fetchone() or {})

    def adjust_credits(
        self,
        org_id: str,
        *,
        delta: float,
        reason: str,
        operation_code: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        tx_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if idempotency_key:
                    cur.execute(
                        """
                        SELECT id::text, balance_after FROM billing.credit_transactions
                        WHERE org_id = %s::uuid AND idempotency_key = %s
                        """,
                        (org_id, idempotency_key),
                    )
                    existing = cur.fetchone()
                    if existing:
                        return dict(existing)

                cur.execute(
                    """
                    UPDATE billing.org_credit_wallets
                    SET balance = balance + %s, updated_at = NOW()
                    WHERE org_id = %s::uuid
                    RETURNING balance
                    """,
                    (delta, org_id),
                )
                wallet_row = cur.fetchone()
                if not wallet_row:
                    raise ValueError("credit wallet not found")
                balance_after = float(wallet_row["balance"])

                cur.execute(
                    """
                    INSERT INTO billing.credit_transactions (
                        id, org_id, delta, balance_after, reason, operation_code,
                        reference_type, reference_id, idempotency_key, metadata
                    ) VALUES (
                        %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s::uuid, %s, %s::jsonb
                    )
                    RETURNING id::text, balance_after
                    """,
                    (
                        tx_id,
                        org_id,
                        delta,
                        balance_after,
                        reason,
                        operation_code,
                        reference_type,
                        reference_id,
                        idempotency_key,
                        Json(metadata or {}),
                    ),
                )
                conn.commit()
                return dict(cur.fetchone() or {})

    def record_ai_usage(
        self,
        org_id: str,
        *,
        provider: str,
        model: str,
        operation_code: str | None,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        credits_charged: float,
        reference_type: str | None = None,
        reference_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        usage_id = str(uuid4())
        total = prompt_tokens + completion_tokens
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO billing.ai_usage (
                        id, org_id, provider, model, operation_code,
                        prompt_tokens, completion_tokens, total_tokens,
                        cost_usd, credits_charged, reference_type, reference_id, metadata
                    ) VALUES (
                        %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::uuid, %s::jsonb
                    )
                    RETURNING id::text
                    """,
                    (
                        usage_id,
                        org_id,
                        provider,
                        model,
                        operation_code,
                        prompt_tokens,
                        completion_tokens,
                        total,
                        cost_usd,
                        credits_charged,
                        reference_type,
                        reference_id,
                        Json(metadata or {}),
                    ),
                )
                conn.commit()
                return dict(cur.fetchone() or {})

    def record_usage_event(
        self,
        org_id: str,
        *,
        metric_code: str,
        delta: int = 1,
        reference_type: str | None = None,
        reference_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        event_id = str(uuid4())
        period = date.today().replace(day=1)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO billing.usage_events (id, org_id, metric_code, delta, reference_type, reference_id, metadata)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s::uuid, %s::jsonb)
                    """,
                    (
                        event_id,
                        org_id,
                        metric_code,
                        delta,
                        reference_type,
                        reference_id,
                        Json(metadata or {}),
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO billing.usage_metrics (id, org_id, metric_code, period_start, value)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s)
                    ON CONFLICT (org_id, metric_code, period_start) DO UPDATE SET
                        value = billing.usage_metrics.value + EXCLUDED.value,
                        updated_at = NOW()
                    """,
                    (str(uuid4()), org_id, metric_code, period, delta),
                )
                conn.commit()

    def get_usage_metric(self, org_id: str, metric_code: str, period_start: date | None = None) -> int:
        if not self.schema_ready():
            return 0
        period = period_start or date.today().replace(day=1)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT value FROM billing.usage_metrics
                    WHERE org_id = %s::uuid AND metric_code = %s AND period_start = %s
                    """,
                    (org_id, metric_code, period),
                )
                row = cur.fetchone()
                return int(row["value"]) if row else 0

    def count_org_users(self, org_id: str) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*)::int AS c FROM core.org_members WHERE org_id = %s::uuid",
                    (org_id,),
                )
                row = cur.fetchone()
                return int(row["c"]) if row else 0

    def count_org_entities(self, org_id: str) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*)::int AS c FROM core.companies WHERE org_id = %s::uuid",
                    (org_id,),
                )
                row = cur.fetchone()
                return int(row["c"]) if row else 0

    def count_org_gstins(self, org_id: str) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT gstin)::int AS c FROM core.companies
                    WHERE org_id = %s::uuid AND gstin IS NOT NULL AND gstin <> ''
                    """,
                    (org_id,),
                )
                row = cur.fetchone()
                return int(row["c"]) if row else 0


billing_repository = BillingRepository()
