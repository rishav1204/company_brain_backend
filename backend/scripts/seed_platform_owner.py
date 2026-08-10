"""Seed the platform-owner (SaaS operator) login.

Creates or updates a single user on the benchmark dev org holding two roles:

  platform_owner  every permission in core.permissions, including
                  ops.worker.manage / ops.queue.manage (ops control plane)
                  and platform.admin (cross-tenant console + commercial
                  control: plan assign, credit grant, entitlement override).
  tenant_admin    role-name gates that check the string rather than a
                  permission, e.g. require_agent_read (/ai/analytics,
                  /ai/gateway/health).

Only these two roles are assigned, on purpose. Assigning every org role — as
seed_e2e_admin_user.py does — unions the ABAC policy_context of all of them, and
ap_preparer carries disallowed_actions ["approve_payment"], which would silently
strip payment approval from the account.

Usage:
  python backend/scripts/seed_platform_owner.py
  python backend/scripts/seed_platform_owner.py --email me@flora.dev --password '...'
  python backend/scripts/seed_platform_owner.py --dsn postgresql://...
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
from argon2 import PasswordHasher

# Benchmark dev org (migrations 004 + 009), where all dev data lives.
ORG_ID = "11111111-1111-4111-8111-111111111111"
COMPANY_ID = "c0000001-0001-4001-8001-000000000001"
BRANCH_ID = "d0000001-0001-4001-8001-000000000001"

OWNER_USER_ID = "0f000001-0001-4001-8001-00000000000f"
DEFAULT_EMAIL = "platform.owner@example.com"
DEFAULT_PASSWORD = "Platform@Owner1"
DISPLAY_NAME = "Platform Owner"

REQUIRED_OPS_PERMISSIONS = ("ops.worker.manage", "ops.queue.manage")


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


def _role_id(cur, org_id: str, role_name: str) -> str | None:
    cur.execute(
        "SELECT id::text FROM core.roles WHERE org_id = %s::uuid AND lower(name) = %s",
        (org_id, role_name),
    )
    row = cur.fetchone()
    return row[0] if row else None


def seed(dsn: str, email: str, password: str) -> dict[str, object]:
    password_hash = PasswordHasher().hash(password)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            _set_org(cur, ORG_ID)

            platform_owner_role = _role_id(cur, ORG_ID, "platform_owner")
            if not platform_owner_role:
                raise SystemExit(
                    "platform_owner role is missing — apply migration 086_platform_owner_role.sql first:\n"
                    "  python backend/scripts/run_migrations.py --dsn <dsn> --migrations-dir backend/migrations"
                )
            tenant_admin_role = _role_id(cur, ORG_ID, "tenant_admin")

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
                (OWNER_USER_ID, ORG_ID, email, DISPLAY_NAME, password_hash),
            )

            # platform_owner stays unscoped: an assignment with no company/branch
            # makes merge_policy_context skip allowed_company_ids/allowed_branch_ids
            # entirely, so no row filter is applied anywhere.
            cur.execute(
                """
                INSERT INTO core.user_roles (org_id, user_id, role_id)
                VALUES (%s::uuid, %s::uuid, %s::uuid)
                ON CONFLICT (user_id, role_id) DO NOTHING
                """,
                (ORG_ID, OWNER_USER_ID, platform_owner_role),
            )
            if tenant_admin_role:
                cur.execute(
                    """
                    INSERT INTO core.user_roles (org_id, user_id, role_id, company_id, branch_id)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid)
                    ON CONFLICT (user_id, role_id) DO UPDATE SET
                        company_id = EXCLUDED.company_id,
                        branch_id = EXCLUDED.branch_id
                    """,
                    (ORG_ID, OWNER_USER_ID, tenant_admin_role, COMPANY_ID, BRANCH_ID),
                )

            _set_org(cur, ORG_ID)
            cur.execute(
                """
                SELECT r.name
                FROM core.user_roles ur
                JOIN core.roles r ON r.id = ur.role_id
                WHERE ur.user_id = %s::uuid
                ORDER BY r.name
                """,
                (OWNER_USER_ID,),
            )
            roles = [row[0] for row in cur.fetchall()]

            cur.execute(
                """
                SELECT DISTINCT p.permission_key
                FROM core.user_roles ur
                JOIN core.role_permissions rp ON rp.role_id = ur.role_id
                JOIN core.permissions p ON p.id = rp.permission_id
                WHERE ur.user_id = %s::uuid
                """,
                (OWNER_USER_ID,),
            )
            permissions = {row[0] for row in cur.fetchall()}

    return {
        "email": email,
        "password": password,
        "org_id": ORG_ID,
        "user_id": OWNER_USER_ID,
        "roles": roles,
        "permission_count": len(permissions),
        "missing_ops": [key for key in REQUIRED_OPS_PERMISSIONS if key not in permissions],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the platform-owner login")
    parser.add_argument("--dsn", help="Postgres DSN (defaults to POSTGRES_DSN from backend/apps/api/.env)")
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    args = parser.parse_args()

    dsn = args.dsn or os.environ.get("POSTGRES_DSN") or _load_dsn_from_env()
    if not dsn:
        print("ERROR: No DSN. Pass --dsn or set POSTGRES_DSN in backend/apps/api/.env", file=sys.stderr)
        return 1

    result = seed(dsn, args.email, args.password)

    print("Platform owner seeded.\n")
    print(f"  Email:       {result['email']}")
    print(f"  Password:    {result['password']}")
    print(f"  Org ID:      {result['org_id']}")
    print(f"  User ID:     {result['user_id']}")
    print(f"  Roles:       {', '.join(result['roles'])}")
    print(f"  Permissions: {result['permission_count']}")
    if result["missing_ops"]:
        print(f"  WARNING missing ops permissions: {', '.join(result['missing_ops'])}")
        print("\nLogin:")
        print("  POST /api/v1/auth/login")
        print(f'  {{"email": "{result["email"]}", "password": "{result["password"]}"}}')
        print("  (org_id optional for unique emails; shared addresses need org_id or org_slug)")
        print(f'  optional: "org_id": "{result["org_id"]}"')
        print("\nThe ops routes in section 1 also need ENABLE_WORKER_ROUTES=true in backend/apps/api/.env")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
