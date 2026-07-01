"""Seed an end-to-end admin user with enterprise plan, billing, and sample analytics data.

Creates (or updates) admin@example.com on the benchmark dev org with all org roles
(except read-only auditor), enterprise subscription, AI credits, sample KPI/dashboard data, and dev workflows.

Usage:
  python backend/scripts/seed_e2e_admin_user.py
  python backend/scripts/seed_e2e_admin_user.py --dsn postgresql://...
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path
from uuid import uuid4

import psycopg
from argon2 import PasswordHasher

# Benchmark dev org (from migrations 004 + 009)
ORG_ID = "11111111-1111-4111-8111-111111111111"
COMPANY_ID = "c0000001-0001-4001-8001-000000000001"
BRANCH_ID = "d0000001-0001-4001-8001-000000000001"
TENANT_ADMIN_ROLE_ID = "b0000001-0001-4001-8001-000000000001"

ADMIN_USER_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin-password"
ADMIN_DISPLAY_NAME = "E2E Admin User"
PLAN_KEY = "enterprise"

KPI_CODES = {
    "treasury.cash_runway_days": 45.0,
    "treasury.liquidity_coverage": 1.25,
    "finance.net_profit_margin": 12.5,
    "collections.dso": 38.0,
    "vendor.dpo": 42.0,
    "compliance.filing_pct": 98.5,
    "close.efficiency_score": 87.0,
    "forecast.accuracy_avg": 91.2,
}


def _load_dsn_from_env() -> str | None:
    env_path = Path(__file__).resolve().parents[1] / "apps" / "api" / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "POSTGRES_DSN":
            return value.strip().strip('"').strip("'")
    return None


def _set_org(cur, org_id: str) -> None:
    cur.execute("SELECT set_config('app.current_org', %s, true)", (org_id,))


def _table_exists(cur, schema: str, table: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
          SELECT 1 FROM information_schema.tables
          WHERE table_schema = %s AND table_name = %s
        )
        """,
        (schema, table),
    )
    return bool(cur.fetchone()[0])


def _assign_all_org_roles(cur, org_id: str, user_id: str, company_id: str, branch_id: str) -> list[str]:
    """Assign every org role except read-only auditor (would lock the admin user)."""
    _set_org(cur, org_id)
    cur.execute(
        """
        SELECT id::text, name
        FROM core.roles
        WHERE org_id = %s::uuid AND lower(name) <> 'auditor'
        ORDER BY name
        """,
        (org_id,),
    )
    assigned: list[str] = []
    for role_id, role_name in cur.fetchall():
        cur.execute(
            """
            INSERT INTO core.user_roles (org_id, user_id, role_id, company_id, branch_id)
            VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid)
            ON CONFLICT (user_id, role_id) DO UPDATE SET
                company_id = EXCLUDED.company_id,
                branch_id = EXCLUDED.branch_id
            """,
            (org_id, user_id, role_id, company_id, branch_id),
        )
        assigned.append(role_name)
    return assigned


def seed(dsn: str) -> dict[str, str]:
    hasher = PasswordHasher()
    password_hash = hasher.hash(ADMIN_PASSWORD)
    snapshot_date = date.today().isoformat()

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            # --- IAM: admin user ---
            _set_org(cur, ORG_ID)
            cur.execute(
                """
                INSERT INTO core.users (id, org_id, email, display_name, status, password_hash, mfa_enabled)
                VALUES (%s::uuid, %s::uuid, %s, %s, 'active', %s, FALSE)
                ON CONFLICT (id) DO UPDATE SET
                    email = EXCLUDED.email,
                    display_name = EXCLUDED.display_name,
                    status = 'active',
                    password_hash = EXCLUDED.password_hash,
                    mfa_enabled = FALSE,
                    updated_at = NOW()
                """,
                (ADMIN_USER_ID, ORG_ID, ADMIN_EMAIL, ADMIN_DISPLAY_NAME, password_hash),
            )

            _assign_all_org_roles(cur, ORG_ID, ADMIN_USER_ID, COMPANY_ID, BRANCH_ID)

            # --- Billing: enterprise plan + credits ---
            if _table_exists(cur, "billing", "org_subscriptions"):
                _set_org(cur, ORG_ID)
                sub_id = str(uuid4())
                cur.execute(
                    """
                    INSERT INTO billing.org_subscriptions (id, org_id, plan_key, status)
                    VALUES (%s::uuid, %s::uuid, %s, 'active')
                    ON CONFLICT (org_id) DO UPDATE SET
                        plan_key = EXCLUDED.plan_key,
                        status = 'active',
                        updated_at = NOW()
                    """,
                    (sub_id, ORG_ID, PLAN_KEY),
                )
                cur.execute(
                    "UPDATE core.organizations SET plan = %s, updated_at = NOW() WHERE id = %s::uuid",
                    (PLAN_KEY, ORG_ID),
                )

            if _table_exists(cur, "billing", "org_credit_wallets"):
                _set_org(cur, ORG_ID)
                wallet_id = str(uuid4())
                cur.execute(
                    """
                    INSERT INTO billing.org_credit_wallets (id, org_id, balance, included_monthly, purchased_balance)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s)
                    ON CONFLICT (org_id) DO UPDATE SET
                        balance = GREATEST(billing.org_credit_wallets.balance, EXCLUDED.balance),
                        included_monthly = EXCLUDED.included_monthly,
                        purchased_balance = GREATEST(
                            billing.org_credit_wallets.purchased_balance, EXCLUDED.purchased_balance
                        ),
                        updated_at = NOW()
                    """,
                    (wallet_id, ORG_ID, 5000.0, 2000.0, 3000.0),
                )

            # --- Analytics sample data ---
            if _table_exists(cur, "finance_analytics", "kpi_snapshots"):
                _set_org(cur, ORG_ID)
                for kpi_code, kpi_value in KPI_CODES.items():
                    cur.execute(
                        """
                        INSERT INTO finance_analytics.kpi_snapshots (org_id, kpi_code, kpi_value, snapshot_date)
                        VALUES (%s::uuid, %s, %s, %s::date)
                        ON CONFLICT (org_id, kpi_code, snapshot_date) DO UPDATE SET
                            kpi_value = EXCLUDED.kpi_value
                        """,
                        (ORG_ID, kpi_code, kpi_value, snapshot_date),
                    )

            if _table_exists(cur, "finance_analytics", "kpi_trends"):
                _set_org(cur, ORG_ID)
                trends = [
                    ("collections.dso", "down", -5.2, "mom"),
                    ("finance.net_profit_margin", "up", 2.1, "mom"),
                    ("treasury.cash_runway_days", "up", 8.0, "mom"),
                ]
                for kpi_code, direction, pct, period_key in trends:
                    cur.execute(
                        """
                        INSERT INTO finance_analytics.kpi_trends
                            (org_id, kpi_code, trend_direction, trend_percent, period_key)
                        VALUES (%s::uuid, %s, %s, %s, %s)
                        ON CONFLICT (org_id, kpi_code, period_key) DO UPDATE SET
                            trend_direction = EXCLUDED.trend_direction,
                            trend_percent = EXCLUDED.trend_percent
                        """,
                        (ORG_ID, kpi_code, direction, pct, period_key),
                    )

            if _table_exists(cur, "finance_analytics", "executive_insights"):
                _set_org(cur, ORG_ID)
                insights = [
                    ("risk", "DSO trending up", "Collections cycle lengthened vs last month.", "warning"),
                    ("opportunity", "Strong liquidity", "Cash runway exceeds 40 days.", "info"),
                    ("risk", "GST filing due", "One return due within 5 days.", "high"),
                ]
                for insight_type, title, description, severity in insights:
                    cur.execute(
                        """
                        INSERT INTO finance_analytics.executive_insights
                            (org_id, insight_type, title, description, severity)
                        SELECT %s::uuid, %s, %s, %s, %s
                        WHERE NOT EXISTS (
                            SELECT 1 FROM finance_analytics.executive_insights
                            WHERE org_id = %s::uuid AND title = %s
                        )
                        """,
                        (ORG_ID, insight_type, title, description, severity, ORG_ID, title),
                    )

            if _table_exists(cur, "finance_analytics", "anomaly_flags"):
                _set_org(cur, ORG_ID)
                cur.execute(
                    """
                    INSERT INTO finance_analytics.anomaly_flags (org_id, anomaly_type, severity, payload)
                    SELECT %s::uuid, 'spend_spike', 'medium', '{"vendor":"Sample Vendor","delta_pct":18}'::jsonb
                    WHERE NOT EXISTS (
                        SELECT 1 FROM finance_analytics.anomaly_flags
                        WHERE org_id = %s::uuid AND anomaly_type = 'spend_spike'
                          AND detected_at > NOW() - INTERVAL '1 day'
                    )
                    """,
                    (ORG_ID, ORG_ID),
                )

            # --- Workflows sample data ---
            if _table_exists(cur, "public", "workflows"):
                cur.execute("SELECT COUNT(*) FROM workflows WHERE org_id = %s::uuid", (ORG_ID,))
                if cur.fetchone()[0] == 0:
                    cur.execute(
                        """
                        INSERT INTO workflows (id, org_id, workflow_type, state, owner_user_id, started_at)
                        VALUES
                          ('33333333-3333-4333-8333-333333333331'::uuid, %s::uuid, 'ap_invoice', 'pending', %s::uuid, NOW()),
                          ('33333333-3333-4333-8333-333333333332'::uuid, %s::uuid, 'ap_invoice', 'pending_approval', %s::uuid, NOW()),
                          ('44444444-4444-4444-8444-444444444441'::uuid, %s::uuid, 'ar_invoice', 'pending', %s::uuid, NOW()),
                          ('55555555-5555-4555-8555-555555555551'::uuid, %s::uuid, 'close_orchestration', 'blocked', %s::uuid, NOW())
                        """,
                        (
                            ORG_ID, ADMIN_USER_ID,
                            ORG_ID, ADMIN_USER_ID,
                            ORG_ID, ADMIN_USER_ID,
                            ORG_ID, ADMIN_USER_ID,
                        ),
                    )

            # --- Verify ---
            _set_org(cur, ORG_ID)
            cur.execute(
                """
                SELECT u.email, u.status, array_agg(DISTINCT r.name) AS roles
                FROM core.users u
                LEFT JOIN core.user_roles ur ON ur.user_id = u.id
                LEFT JOIN core.roles r ON r.id = ur.role_id
                WHERE u.id = %s::uuid
                GROUP BY u.email, u.status
                """,
                (ADMIN_USER_ID,),
            )
            user_row = cur.fetchone()
            roles = user_row[2] if user_row else []

            plan = None
            if _table_exists(cur, "billing", "org_subscriptions"):
                _set_org(cur, ORG_ID)
                cur.execute(
                    "SELECT plan_key, status FROM billing.org_subscriptions WHERE org_id = %s::uuid",
                    (ORG_ID,),
                )
                sub = cur.fetchone()
                plan = f"{sub[0]} ({sub[1]})" if sub else "missing"

            cur.execute(
                """
                SELECT COUNT(*) FROM core.role_permissions rp
                JOIN core.user_roles ur ON ur.role_id = rp.role_id
                WHERE ur.user_id = %s::uuid
                """,
                (ADMIN_USER_ID,),
            )
            permission_count = cur.fetchone()[0]

    return {
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
        "org_id": ORG_ID,
        "user_id": ADMIN_USER_ID,
        "roles": ", ".join(roles) if roles else "none",
        "permissions": str(permission_count),
        "plan": plan or "n/a (billing schema missing)",
        "snapshot_date": snapshot_date,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed E2E admin user with enterprise plan and sample data")
    parser.add_argument("--dsn", help="Postgres DSN (defaults to POSTGRES_DSN from backend/apps/api/.env)")
    args = parser.parse_args()

    dsn = args.dsn or os.environ.get("POSTGRES_DSN") or _load_dsn_from_env()
    if not dsn:
        print("ERROR: No DSN. Pass --dsn or set POSTGRES_DSN in backend/apps/api/.env", file=sys.stderr)
        return 1

    try:
        result = seed(dsn)
    except Exception as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("E2E admin user seeded successfully.\n")
    print("Login credentials:")
    print(f"  Email:    {result['email']}")
    print(f"  Password: {result['password']}")
    print(f"  Org ID:   {result['org_id']}")
    print(f"  User ID:  {result['user_id']}")
    print(f"  Roles:    {result['roles']}")
    print(f"  Permissions (via roles): {result['permissions']}")
    print(f"  Plan:     {result['plan']}")
    print(f"  Analytics snapshot date: {result['snapshot_date']}")
    print("\nAPI login:")
    print('  POST /api/v1/auth/login')
    print(f'  {{"email": "{result["email"]}", "password": "{result["password"]}", "mfa_code": null}}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
