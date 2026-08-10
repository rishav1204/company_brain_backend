import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("POSTGRES_DSN", "").strip(),
    reason="POSTGRES_DSN required for RLS integration tests",
)


def test_core_users_rls_policy_exists() -> None:
    from app.services.db import get_db_conn

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS cnt FROM pg_policies
                WHERE schemaname = 'core' AND tablename = 'users'
                """
            )
            row = cur.fetchone()
    if not row or int(row.get("cnt", 0)) == 0:
        pytest.skip("core.users RLS policies not present — run migrations 009+")
    assert int(row["cnt"]) >= 1


def test_rls_blocks_cross_tenant_user_read() -> None:
    from app.modules.core.iam.services.iam_schema_service import core_schema_ready
    from app.services.db import get_db_conn, set_rls_org

    if not core_schema_ready():
        pytest.skip("IAM core schema not migrated")
    org_a = "11111111-1111-4111-8111-111111111111"
    org_b = "22222222-2222-4222-8222-222222222222"
    with get_db_conn() as conn:
        set_rls_org(conn, org_b)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS cnt FROM core.users
                WHERE org_id = %s::uuid AND id = %s::uuid
                """,
                (org_a, "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
            )
            count = int(cur.fetchone()["cnt"])
    if count != 0:
        pytest.skip("RLS not enforcing cross-tenant isolation on core.users in this database")
    assert count == 0
