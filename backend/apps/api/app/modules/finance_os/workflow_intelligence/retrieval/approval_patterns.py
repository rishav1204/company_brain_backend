from __future__ import annotations

from app.services.db import get_db_conn, set_rls_org


def approval_pass_through_rates(org_id: str, *, workflow_type: str | None = None, days: int = 90) -> dict[str, float]:
    with get_db_conn() as conn:
        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            if workflow_type:
                cur.execute(
                    """
                    SELECT ws.step_key,
                           COUNT(*) FILTER (WHERE a.decision = 'approved')::float /
                           NULLIF(COUNT(*)::float, 0) AS pass_rate
                    FROM workflow.approvals a
                    JOIN workflow.workflow_steps ws ON ws.id = a.workflow_step_id
                    JOIN workflow.workflow_instances wi ON wi.id = a.workflow_instance_id
                    WHERE a.org_id = %s::uuid AND wi.workflow_type = %s
                      AND a.created_at >= NOW() - (%s || ' days')::interval
                    GROUP BY ws.step_key
                    """,
                    (org_id, workflow_type, days),
                )
            else:
                cur.execute(
                    """
                    SELECT ws.step_key,
                           COUNT(*) FILTER (WHERE a.decision = 'approved')::float /
                           NULLIF(COUNT(*)::float, 0) AS pass_rate
                    FROM workflow.approvals a
                    JOIN workflow.workflow_steps ws ON ws.id = a.workflow_step_id
                    WHERE a.org_id = %s::uuid
                      AND a.created_at >= NOW() - (%s || ' days')::interval
                    GROUP BY ws.step_key
                    """,
                    (org_id, days),
                )
            return {str(r["step_key"]): float(r["pass_rate"] or 0) for r in cur.fetchall()}


def rejection_rates(org_id: str, *, workflow_type: str | None = None, days: int = 90) -> dict[str, float]:
    with get_db_conn() as conn:
        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            if workflow_type:
                cur.execute(
                    """
                    SELECT ws.step_key,
                           COUNT(*) FILTER (WHERE a.decision = 'rejected')::float /
                           NULLIF(COUNT(*)::float, 0) AS rej_rate
                    FROM workflow.approvals a
                    JOIN workflow.workflow_steps ws ON ws.id = a.workflow_step_id
                    JOIN workflow.workflow_instances wi ON wi.id = a.workflow_instance_id
                    WHERE a.org_id = %s::uuid AND wi.workflow_type = %s
                      AND a.created_at >= NOW() - (%s || ' days')::interval
                    GROUP BY ws.step_key
                    """,
                    (org_id, workflow_type, days),
                )
            else:
                cur.execute(
                    """
                    SELECT ws.step_key,
                           COUNT(*) FILTER (WHERE a.decision = 'rejected')::float /
                           NULLIF(COUNT(*)::float, 0) AS rej_rate
                    FROM workflow.approvals a
                    JOIN workflow.workflow_steps ws ON ws.id = a.workflow_step_id
                    WHERE a.org_id = %s::uuid
                      AND a.created_at >= NOW() - (%s || ' days')::interval
                    GROUP BY ws.step_key
                    """,
                    (org_id, days),
                )
            return {str(r["step_key"]): float(r["rej_rate"] or 0) for r in cur.fetchall()}
