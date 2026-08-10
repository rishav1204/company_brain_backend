"""Cross-org reads for the platform operator console.

These queries deliberately omit ``set_rls_org``: they span every tenant, so
there is no single org to pin the RLS GUC to. That works today because the
application's database role can see all rows. If you ever move the app onto a
least-privilege role that RLS actually constrains, these queries return empty
rather than erroring — give that role BYPASSRLS, or add a policy exception, and
keep the tenant-scoped repositories on the restricted role.

Persistence only: no permission checks, no event publishing. The caller
(operator_service) owns authorisation and audit.
"""
from typing import Any

from app.services.db import get_db_conn
from app.services.repository_pagination import clamp_limit, clamp_offset

_USAGE_METRIC_CODES = ("users", "entities", "api_calls", "invoices", "workflow_runs")


def _table_exists(cur, schema: str, table: str) -> bool:
    cur.execute("SELECT to_regclass(%s) AS reg", (f"{schema}.{table}",))
    return cur.fetchone()["reg"] is not None


class OperatorRepository:
    def list_organizations(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        limit = clamp_limit(limit, default=100, maximum=500)
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT o.id::text AS id,
                           o.id::text AS org_id,
                           o.name,
                           o.slug,
                           o.plan,
                           o.plan AS plan_key,
                           o.status,
                           o.country_code,
                           o.currency,
                           o.created_at,
                           COUNT(u.id) FILTER (WHERE u.status = 'active') AS active_users,
                           COUNT(u.id) AS total_users
                    FROM core.organizations o
                    LEFT JOIN core.users u ON u.org_id = o.id
                    GROUP BY o.id, o.name, o.slug, o.plan, o.status,
                             o.country_code, o.currency, o.created_at
                    ORDER BY o.created_at ASC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, clamp_offset(offset)),
                )
                return list(cur.fetchall())

    def count_organizations(self) -> int:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM core.organizations")
                return int(cur.fetchone()["c"])

    def list_users(
        self,
        *,
        org_id: str | None = None,
        status: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        limit = clamp_limit(limit, default=50, maximum=500)
        clauses: list[str] = []
        params: list[Any] = []
        if org_id:
            clauses.append("u.org_id = %s::uuid")
            params.append(org_id)
        if status:
            clauses.append("u.status = %s")
            params.append(status)
        if search:
            clauses.append("(u.email ILIKE %s OR u.display_name ILIKE %s)")
            term = f"%{search.strip()}%"
            params.extend([term, term])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, clamp_offset(offset)])

        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT u.id::text AS user_id,
                           u.org_id::text AS org_id,
                           o.name AS org_name,
                           u.email,
                           u.display_name,
                           u.status,
                           u.mfa_enabled,
                           u.last_login_at,
                           u.created_at,
                           -- DISTINCT is load-bearing: joining user_roles and
                           -- sessions together multiplies rows, so a plain
                           -- ARRAY_AGG repeats each role once per session.
                           COALESCE(
                               ARRAY_AGG(DISTINCT r.name) FILTER (WHERE r.name IS NOT NULL),
                               '{{}}'
                           ) AS roles,
                           COUNT(DISTINCT s.id) FILTER (
                               WHERE s.revoked = FALSE AND s.expires_at > NOW()
                           ) AS active_sessions
                    FROM core.users u
                    JOIN core.organizations o ON o.id = u.org_id
                    LEFT JOIN core.user_roles ur ON ur.user_id = u.id
                    LEFT JOIN core.roles r ON r.id = ur.role_id
                    LEFT JOIN core.sessions s ON s.user_id = u.id
                    {where}
                    GROUP BY u.id, u.org_id, o.name, u.email, u.display_name,
                             u.status, u.mfa_enabled, u.last_login_at, u.created_at
                    ORDER BY u.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(params),
                )
                return list(cur.fetchall())

    def count_users(
        self,
        *,
        org_id: str | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> int:
        clauses: list[str] = []
        params: list[Any] = []
        if org_id:
            clauses.append("org_id = %s::uuid")
            params.append(org_id)
        if status:
            clauses.append("status = %s")
            params.append(status)
        if search:
            clauses.append("(email ILIKE %s OR display_name ILIKE %s)")
            term = f"%{search.strip()}%"
            params.extend([term, term])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) AS c FROM core.users {where}", tuple(params))
                return int(cur.fetchone()["c"])

    def find_user(self, user_id: str) -> dict[str, Any] | None:
        """Resolve a user without knowing their org — the entry point for every
        cross-org mutation, which then re-enters the normal org-scoped repos."""
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.id::text AS user_id,
                           u.org_id::text AS org_id,
                           o.name AS org_name,
                           u.email,
                           u.display_name,
                           u.status
                    FROM core.users u
                    JOIN core.organizations o ON o.id = u.org_id
                    WHERE u.id = %s::uuid
                    """,
                    (user_id,),
                )
                return cur.fetchone()

    def usage_by_org(self, *, days: int = 30, limit: int = 100) -> list[dict[str, Any]]:
        """Per-org usage rollup. Each source is optional: a partially migrated
        database should still return the org list with the metrics it does have."""
        limit = clamp_limit(limit, default=100, maximum=500)
        window_days = max(1, min(int(days), 365))

        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT o.id::text AS org_id, o.name, o.plan, o.status,
                           COUNT(u.id) FILTER (WHERE u.status = 'active') AS active_users
                    FROM core.organizations o
                    LEFT JOIN core.users u ON u.org_id = o.id
                    GROUP BY o.id, o.name, o.plan, o.status
                    ORDER BY o.created_at ASC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = {row["org_id"]: dict(row) for row in cur.fetchall()}
                for row in rows.values():
                    row.update(
                        ai_requests=0,
                        ai_tokens=0,
                        ai_cost_usd=0.0,
                        api_calls=0,
                        metrics={},
                        window_days=window_days,
                    )

                if _table_exists(cur, "billing", "ai_usage"):
                    cur.execute(
                        """
                        SELECT org_id::text AS org_id,
                               COUNT(*) AS ai_requests,
                               COALESCE(SUM(total_tokens), 0) AS ai_tokens,
                               COALESCE(SUM(cost_usd), 0) AS ai_cost_usd
                        FROM billing.ai_usage
                        WHERE created_at > NOW() - make_interval(days => %s)
                        GROUP BY org_id
                        """,
                        (window_days,),
                    )
                    for row in cur.fetchall():
                        target = rows.get(row["org_id"])
                        if target:
                            target["ai_requests"] = int(row["ai_requests"])
                            target["ai_tokens"] = int(row["ai_tokens"])
                            target["ai_cost_usd"] = float(row["ai_cost_usd"])

                if _table_exists(cur, "platform", "api_request_log"):
                    cur.execute(
                        """
                        SELECT org_id::text AS org_id, COUNT(*) AS api_calls
                        FROM platform.api_request_log
                        WHERE created_at > NOW() - make_interval(days => %s)
                        GROUP BY org_id
                        """,
                        (window_days,),
                    )
                    for row in cur.fetchall():
                        target = rows.get(row["org_id"])
                        if target:
                            target["api_calls"] = int(row["api_calls"])

                if _table_exists(cur, "billing", "usage_metrics"):
                    cur.execute(
                        """
                        SELECT org_id::text AS org_id, metric_code, SUM(value) AS value
                        FROM billing.usage_metrics
                        WHERE metric_code = ANY(%s)
                        GROUP BY org_id, metric_code
                        """,
                        (list(_USAGE_METRIC_CODES),),
                    )
                    for row in cur.fetchall():
                        target = rows.get(row["org_id"])
                        if target:
                            target["metrics"][row["metric_code"]] = int(row["value"])

                return list(rows.values())


operator_repository = OperatorRepository()
