from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org
from app.services.repository_pagination import clamp_limit


class GoalRepository:
    def schema_ready(self) -> bool:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'finance_os' AND table_name = 'goals'
                    LIMIT 1
                    """
                )
                return cur.fetchone() is not None

    def create_goal(
        self,
        org_id: str,
        *,
        title: str,
        description: str | None,
        trigger_type: str,
        world_state: dict,
        plan_metadata: dict,
        created_by: str | None,
        goal_type: str = "user",
        trigger_config: dict | None = None,
        status: str = "active",
    ) -> dict:
        gid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        INSERT INTO finance_os.goals (
                          id, org_id, goal_type, title, description, status, trigger_type,
                          trigger_config, world_state, plan_metadata, created_by
                        )
                        VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
                        RETURNING id::text, title, status, created_at::text
                        """,
                        (
                            gid,
                            org_id,
                            goal_type,
                            title,
                            description,
                            status,
                            trigger_type,
                            Json(trigger_config or {}),
                            Json(world_state),
                            Json(plan_metadata),
                            created_by,
                        ),
                    )
                except Exception:
                    cur.execute(
                        """
                        INSERT INTO finance_os.goals (
                          id, org_id, goal_type, title, description, status, trigger_type,
                          world_state, plan_metadata, created_by
                        )
                        VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                        RETURNING id::text, title, status, created_at::text
                        """,
                        (
                            gid,
                            org_id,
                            goal_type,
                            title,
                            description,
                            status,
                            trigger_type,
                            Json(world_state),
                            Json(plan_metadata),
                            created_by,
                        ),
                    )
                return dict(cur.fetchone() or {"id": gid})

    def get_goal(self, org_id: str, goal_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        SELECT id::text, title, description, status, goal_type, trigger_type,
                               trigger_config, world_state, plan_metadata, conversation_state,
                               created_by, created_at::text
                        FROM finance_os.goals WHERE org_id = %s::uuid AND id = %s::uuid
                        """,
                        (org_id, goal_id),
                    )
                except Exception:
                    try:
                        cur.execute(
                            """
                            SELECT id::text, title, description, status, trigger_type,
                                   world_state, plan_metadata, conversation_state, created_by, created_at::text
                            FROM finance_os.goals WHERE org_id = %s::uuid AND id = %s::uuid
                            """,
                            (org_id, goal_id),
                        )
                    except Exception:
                        cur.execute(
                            """
                            SELECT id::text, title, description, status, trigger_type,
                                   world_state, plan_metadata, created_by, created_at::text
                            FROM finance_os.goals WHERE org_id = %s::uuid AND id = %s::uuid
                            """,
                            (org_id, goal_id),
                        )
                row = cur.fetchone()
                if not row:
                    return None
                data = dict(row)
                if data.get("conversation_state") is None:
                    data["conversation_state"] = {}
                if data.get("trigger_config") is None:
                    data["trigger_config"] = {}
                return data

    def update_trigger_config(self, org_id: str, goal_id: str, trigger_config: dict) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        UPDATE finance_os.goals
                        SET trigger_config = %s::jsonb, updated_at = NOW()
                        WHERE org_id = %s::uuid AND id = %s::uuid
                        """,
                        (Json(trigger_config), org_id, goal_id),
                    )
                except Exception:
                    pass

    def merge_plan_metadata(self, org_id: str, goal_id: str, patch: dict) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        UPDATE finance_os.goals
                        SET plan_metadata = COALESCE(plan_metadata, '{}'::jsonb) || %s::jsonb,
                            updated_at = NOW()
                        WHERE org_id = %s::uuid AND id = %s::uuid
                        """,
                        (Json(patch), org_id, goal_id),
                    )
                except Exception:
                    pass

    def update_conversation_state(self, org_id: str, goal_id: str, state: dict) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        UPDATE finance_os.goals
                        SET conversation_state = %s::jsonb, updated_at = NOW()
                        WHERE org_id = %s::uuid AND id = %s::uuid
                        """,
                        (Json(state), org_id, goal_id),
                    )
                except Exception:
                    pass

    def update_world_state(self, org_id: str, goal_id: str, world_state: dict) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        UPDATE finance_os.goals
                        SET world_state = %s::jsonb, updated_at = NOW()
                        WHERE org_id = %s::uuid AND id = %s::uuid
                        """,
                        (Json(world_state), org_id, goal_id),
                    )
                except Exception:
                    pass

    def update_goal_status(self, org_id: str, goal_id: str, *, status: str) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE finance_os.goals
                    SET status = %s, updated_at = NOW(),
                        completed_at = CASE WHEN %s IN ('completed', 'failed', 'cancelled') THEN NOW() ELSE completed_at END
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (status, status, org_id, goal_id),
                )

    def create_run(
        self,
        org_id: str,
        *,
        goal_id: str,
        metadata: dict | None = None,
        confidence_score: float | None = None,
        risk_level: str | None = None,
    ) -> dict:
        rid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_os.goal_runs (
                      id, org_id, goal_id, status, metadata, confidence_score, risk_level
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, 'running', %s::jsonb, %s, %s)
                    RETURNING id::text, goal_id::text, status, started_at::text
                    """,
                    (rid, org_id, goal_id, Json(metadata or {}), confidence_score, risk_level),
                )
                return dict(cur.fetchone() or {"id": rid})

    def get_run(self, org_id: str, run_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, goal_id::text, status, current_node_id, human_approved,
                           confidence_score, risk_level, metadata, started_at::text, completed_at::text
                    FROM finance_os.goal_runs WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, run_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def update_run(
        self,
        org_id: str,
        run_id: str,
        *,
        status: str | None = None,
        current_node_id: str | None = None,
        human_approved: bool | None = None,
        metadata: dict | None = None,
    ) -> None:
        fields: list[str] = []
        params: list = []
        if status is not None:
            fields.append("status = %s")
            params.append(status)
            if status in {"completed", "failed", "pending_approval", "cancelled"}:
                fields.append("completed_at = CASE WHEN %s IN ('completed', 'failed', 'cancelled') THEN NOW() ELSE completed_at END")
                params.append(status)
        if current_node_id is not None:
            fields.append("current_node_id = %s")
            params.append(current_node_id)
        if human_approved is not None:
            fields.append("human_approved = %s")
            params.append(human_approved)
        if metadata is not None:
            fields.append("metadata = metadata || %s::jsonb")
            params.append(Json(metadata))
        if not fields:
            return
        params.extend([org_id, run_id])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE finance_os.goal_runs SET {', '.join(fields)} WHERE org_id = %s::uuid AND id = %s::uuid",
                    tuple(params),
                )

    def save_graph(
        self,
        org_id: str,
        *,
        goal_run_id: str,
        graph: dict,
        reasoning: str | None = None,
        rollback_strategy: list | None = None,
    ) -> dict:
        gid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_os.execution_graphs (
                      id, org_id, goal_run_id, nodes, edges, reasoning, rollback_strategy
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::jsonb, %s::jsonb, %s, %s::jsonb)
                    RETURNING id::text
                    """,
                    (
                        gid,
                        org_id,
                        goal_run_id,
                        Json(graph.get("nodes") or []),
                        Json(graph.get("edges") or []),
                        reasoning,
                        Json(rollback_strategy or []),
                    ),
                )
                return dict(cur.fetchone() or {"id": gid})

    def get_latest_graph(self, org_id: str, goal_run_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, nodes, edges, reasoning, rollback_strategy
                    FROM finance_os.execution_graphs
                    WHERE org_id = %s::uuid AND goal_run_id = %s::uuid
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (org_id, goal_run_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "id": row["id"],
                    "nodes": row["nodes"],
                    "edges": row["edges"],
                    "reasoning": row["reasoning"],
                    "rollback_strategy": row["rollback_strategy"],
                }

    def save_observation(
        self,
        org_id: str,
        *,
        goal_run_id: str,
        node_id: str,
        tool_name: str,
        tool_method: str,
        status: str,
        result: dict,
        alternatives: list | None = None,
    ) -> None:
        oid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_os.runtime_observations (
                      id, org_id, goal_run_id, node_id, tool_name, tool_method, status, result, alternatives
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                    """,
                    (oid, org_id, goal_run_id, node_id, tool_name, tool_method, status, Json(result), Json(alternatives or [])),
                )

    def list_observations(self, org_id: str, goal_run_id: str, *, limit: int = 50) -> list[dict]:
        limit = clamp_limit(limit, default=50, maximum=200)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT node_id, tool_name, tool_method, status, result, alternatives, created_at::text
                    FROM finance_os.runtime_observations
                    WHERE org_id = %s::uuid AND goal_run_id = %s::uuid
                    ORDER BY created_at ASC LIMIT %s
                    """,
                    (org_id, goal_run_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]

    def list_goals(self, org_id: str, *, status: str | None = None, limit: int = 50) -> list[dict]:
        limit = clamp_limit(limit, default=50, maximum=200)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if status:
                    cur.execute(
                        """
                        SELECT id::text, title, status, trigger_type, created_at::text
                        FROM finance_os.goals
                        WHERE org_id = %s::uuid AND status = %s
                        ORDER BY created_at DESC LIMIT %s
                        """,
                        (org_id, status, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, title, status, trigger_type, created_at::text
                        FROM finance_os.goals
                        WHERE org_id = %s::uuid
                        ORDER BY created_at DESC LIMIT %s
                        """,
                        (org_id, limit),
                    )
                return [dict(r) for r in cur.fetchall()]

    def list_goals_detailed(
        self,
        org_id: str,
        *,
        status: str | None = None,
        goal_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Active watchers / operational goals with world_state + trigger_config (Wave 5)."""
        limit = clamp_limit(limit, default=50, maximum=200)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                try:
                    clauses = ["org_id = %s::uuid"]
                    params: list = [org_id]
                    if status:
                        clauses.append("status = %s")
                        params.append(status)
                    if goal_type:
                        clauses.append("goal_type = %s")
                        params.append(goal_type)
                    params.append(limit)
                    cur.execute(
                        f"""
                        SELECT id::text, title, status, goal_type, trigger_type, trigger_config,
                               world_state, plan_metadata, created_at::text
                        FROM finance_os.goals
                        WHERE {' AND '.join(clauses)}
                        ORDER BY created_at DESC LIMIT %s
                        """,
                        tuple(params),
                    )
                    return [dict(r) for r in cur.fetchall()]
                except Exception:
                    return self.list_goals(org_id, status=status, limit=limit)

    def get_latest_run(self, org_id: str, goal_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, goal_id::text, status, current_node_id, human_approved,
                           confidence_score, risk_level, metadata, started_at::text, completed_at::text
                    FROM finance_os.goal_runs
                    WHERE org_id = %s::uuid AND goal_id = %s::uuid
                    ORDER BY started_at DESC LIMIT 1
                    """,
                    (org_id, goal_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list_pending_runs(self, org_id: str, *, limit: int = 50) -> list[dict]:
        limit = clamp_limit(limit, default=50, maximum=200)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT r.id::text AS run_id, r.goal_id::text, r.status, r.current_node_id,
                           r.risk_level, r.started_at::text, g.title
                    FROM finance_os.goal_runs r
                    JOIN finance_os.goals g ON g.id = r.goal_id
                    WHERE r.org_id = %s::uuid
                      AND r.status IN ('pending_approval', 'blocked', 'running')
                    ORDER BY r.started_at DESC LIMIT %s
                    """,
                    (org_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]


goal_repository = GoalRepository()
