"""Platform control-plane repository: catalog, org/user controls, support, activity, recycle."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org
from app.services.repository_pagination import clamp_limit, clamp_offset
from app.services.schema_registry import table_ready


class ControlPlaneRepository:
    def feature_catalog_ready(self) -> bool:
        return table_ready("platform", "feature_catalog")

    def list_features(self) -> list[dict[str, Any]]:
        if not self.feature_catalog_ready():
            return []
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT feature_code, name, description, category, is_ai, parent_code,
                           depends_on, risk_level, status, metadata
                    FROM platform.feature_catalog
                    ORDER BY category, feature_code
                    """
                )
                return [dict(r) for r in cur.fetchall()]

    def upsert_feature(self, payload: dict[str, Any]) -> dict[str, Any]:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO platform.feature_catalog (
                        feature_code, name, description, category, is_ai, parent_code,
                        depends_on, risk_level, status, metadata, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, NOW()
                    )
                    ON CONFLICT (feature_code) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        category = EXCLUDED.category,
                        is_ai = EXCLUDED.is_ai,
                        parent_code = EXCLUDED.parent_code,
                        depends_on = EXCLUDED.depends_on,
                        risk_level = EXCLUDED.risk_level,
                        status = EXCLUDED.status,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    RETURNING feature_code, name, category, is_ai, status
                    """,
                    (
                        payload["feature_code"],
                        payload.get("name") or payload["feature_code"],
                        payload.get("description"),
                        payload.get("category") or "erp",
                        bool(payload.get("is_ai", False)),
                        payload.get("parent_code"),
                        Json(payload.get("depends_on") or []),
                        int(payload.get("risk_level") or 0),
                        payload.get("status") or "active",
                        Json(payload.get("metadata") or {}),
                    ),
                )
                row = dict(cur.fetchone() or {})
                conn.commit()
                return row

    def list_screens(self) -> list[dict[str, Any]]:
        if not table_ready("platform", "ui_screen_registry"):
            return []
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT screen_key, route_path, label, nav_category, feature_code,
                           permission_key, console, sort_order, status, metadata
                    FROM platform.ui_screen_registry
                    WHERE status = 'active'
                    ORDER BY sort_order, screen_key
                    """
                )
                return [dict(r) for r in cur.fetchall()]

    def upsert_screen(self, payload: dict[str, Any]) -> dict[str, Any]:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO platform.ui_screen_registry (
                        screen_key, route_path, label, nav_category, feature_code,
                        permission_key, console, sort_order, status, metadata, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW()
                    )
                    ON CONFLICT (screen_key) DO UPDATE SET
                        route_path = EXCLUDED.route_path,
                        label = EXCLUDED.label,
                        nav_category = EXCLUDED.nav_category,
                        feature_code = EXCLUDED.feature_code,
                        permission_key = EXCLUDED.permission_key,
                        console = EXCLUDED.console,
                        sort_order = EXCLUDED.sort_order,
                        status = EXCLUDED.status,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    RETURNING screen_key, route_path, label, feature_code, permission_key, console
                    """,
                    (
                        payload["screen_key"],
                        payload["route_path"],
                        payload.get("label") or payload["screen_key"],
                        payload.get("nav_category"),
                        payload.get("feature_code"),
                        payload.get("permission_key"),
                        payload.get("console") or "erp",
                        int(payload.get("sort_order") or 0),
                        payload.get("status") or "active",
                        Json(payload.get("metadata") or {}),
                    ),
                )
                row = dict(cur.fetchone() or {})
                conn.commit()
                return row

    def get_org_controls(self, org_id: str) -> dict[str, Any] | None:
        if not table_ready("platform", "org_controls"):
            return None
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT org_id::text, lifecycle_status, login_allowed, ai_enabled,
                           erp_modules_enabled, api_access_allowed, support_priority,
                           notes, updated_by::text, updated_at, metadata
                    FROM platform.org_controls WHERE org_id = %s::uuid
                    """,
                    (org_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def upsert_org_controls(self, org_id: str, fields: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        existing = self.get_org_controls(org_id) or {}
        lifecycle = fields.get("lifecycle_status", existing.get("lifecycle_status") or "active")
        login_allowed = fields.get("login_allowed", existing.get("login_allowed", True))
        ai_enabled = fields.get("ai_enabled", existing.get("ai_enabled", True))
        erp_modules_enabled = fields.get("erp_modules_enabled", existing.get("erp_modules_enabled", True))
        api_access_allowed = fields.get("api_access_allowed", existing.get("api_access_allowed", True))
        support_priority = fields.get("support_priority", existing.get("support_priority") or "standard")
        notes = fields.get("notes", existing.get("notes"))
        metadata = fields.get("metadata", existing.get("metadata") or {})
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO platform.org_controls (
                        org_id, lifecycle_status, login_allowed, ai_enabled, erp_modules_enabled,
                        api_access_allowed, support_priority, notes, updated_by, updated_at, metadata
                    ) VALUES (
                        %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s::uuid, NOW(), %s::jsonb
                    )
                    ON CONFLICT (org_id) DO UPDATE SET
                        lifecycle_status = EXCLUDED.lifecycle_status,
                        login_allowed = EXCLUDED.login_allowed,
                        ai_enabled = EXCLUDED.ai_enabled,
                        erp_modules_enabled = EXCLUDED.erp_modules_enabled,
                        api_access_allowed = EXCLUDED.api_access_allowed,
                        support_priority = EXCLUDED.support_priority,
                        notes = EXCLUDED.notes,
                        updated_by = EXCLUDED.updated_by,
                        updated_at = NOW(),
                        metadata = EXCLUDED.metadata
                    RETURNING org_id::text, lifecycle_status, login_allowed, ai_enabled,
                              erp_modules_enabled, api_access_allowed, support_priority, notes, updated_at
                    """,
                    (
                        org_id,
                        lifecycle,
                        bool(login_allowed),
                        bool(ai_enabled),
                        bool(erp_modules_enabled),
                        bool(api_access_allowed),
                        support_priority,
                        notes,
                        actor_id,
                        Json(metadata if isinstance(metadata, dict) else {}),
                    ),
                )
                row = dict(cur.fetchone() or {})
                conn.commit()
                return row

    def get_user_controls(self, org_id: str, user_id: str) -> dict[str, Any] | None:
        if not table_ready("platform", "user_controls"):
            return None
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, org_id::text, user_id::text, denied_feature_codes,
                           denied_screen_keys, force_read_only, reason, source, expires_at
                    FROM platform.user_controls
                    WHERE org_id = %s::uuid AND user_id = %s::uuid
                      AND (expires_at IS NULL OR expires_at > NOW())
                    """,
                    (org_id, user_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def upsert_user_controls(
        self,
        org_id: str,
        user_id: str,
        fields: dict[str, Any],
        *,
        actor_id: str | None,
    ) -> dict[str, Any]:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO platform.user_controls (
                        id, org_id, user_id, denied_feature_codes, denied_screen_keys,
                        force_read_only, reason, source, expires_at, created_by, updated_at
                    ) VALUES (
                        %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s::uuid, NOW()
                    )
                    ON CONFLICT (org_id, user_id) DO UPDATE SET
                        denied_feature_codes = EXCLUDED.denied_feature_codes,
                        denied_screen_keys = EXCLUDED.denied_screen_keys,
                        force_read_only = EXCLUDED.force_read_only,
                        reason = EXCLUDED.reason,
                        source = EXCLUDED.source,
                        expires_at = EXCLUDED.expires_at,
                        updated_at = NOW()
                    RETURNING id::text, org_id::text, user_id::text, denied_feature_codes,
                              denied_screen_keys, force_read_only, reason, source
                    """,
                    (
                        str(uuid4()),
                        org_id,
                        user_id,
                        list(fields.get("denied_feature_codes") or []),
                        list(fields.get("denied_screen_keys") or []),
                        bool(fields.get("force_read_only", False)),
                        fields.get("reason"),
                        fields.get("source") or "platform_owner",
                        fields.get("expires_at"),
                        actor_id,
                    ),
                )
                row = dict(cur.fetchone() or {})
                conn.commit()
                return row

    # --- Support ---

    def create_ticket(self, org_id: str, *, user_id: str, subject: str, category: str, priority: str, body: str) -> dict[str, Any]:
        ticket_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO support.tickets (
                        id, org_id, created_by_user_id, subject, category, priority, status
                    ) VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, 'open')
                    RETURNING id::text, org_id::text, subject, category, priority, status, created_at
                    """,
                    (ticket_id, org_id, user_id, subject, category, priority),
                )
                ticket = dict(cur.fetchone() or {})
                cur.execute(
                    """
                    INSERT INTO support.messages (id, ticket_id, org_id, author_user_id, author_side, body)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, 'customer', %s)
                    """,
                    (str(uuid4()), ticket_id, org_id, user_id, body),
                )
                conn.commit()
                return ticket

    def list_tickets(
        self,
        *,
        org_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if not table_ready("support", "tickets"):
            return []
        clauses: list[str] = []
        params: list[Any] = []
        if org_id:
            clauses.append("org_id = %s::uuid")
            params.append(org_id)
        if status:
            clauses.append("status = %s")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([clamp_limit(limit), clamp_offset(offset)])
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, org_id::text, created_by_user_id::text, assigned_to_user_id::text,
                           subject, category, priority, status, created_at, updated_at
                    FROM support.tickets
                    {where}
                    ORDER BY updated_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in cur.fetchall()]

    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, org_id::text, created_by_user_id::text, assigned_to_user_id::text,
                           subject, category, priority, status, related_feature_code, created_at, updated_at
                    FROM support.tickets WHERE id = %s::uuid
                    """,
                    (ticket_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def add_message(
        self,
        *,
        ticket_id: str,
        org_id: str,
        author_user_id: str,
        author_side: str,
        body: str,
    ) -> dict[str, Any]:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO support.messages (id, ticket_id, org_id, author_user_id, author_side, body)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s)
                    RETURNING id::text, ticket_id::text, author_side, body, created_at
                    """,
                    (str(uuid4()), ticket_id, org_id, author_user_id, author_side, body),
                )
                msg = dict(cur.fetchone() or {})
                cur.execute(
                    "UPDATE support.tickets SET updated_at = NOW() WHERE id = %s::uuid",
                    (ticket_id,),
                )
                conn.commit()
                return msg

    def list_messages(self, ticket_id: str) -> list[dict[str, Any]]:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, author_user_id::text, author_side, body, attachments, created_at
                    FROM support.messages WHERE ticket_id = %s::uuid
                    ORDER BY created_at ASC
                    """,
                    (ticket_id,),
                )
                return [dict(r) for r in cur.fetchall()]

    def update_ticket_status(
        self, ticket_id: str, *, status: str, assigned_to: str | None = None
    ) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                if assigned_to is not None:
                    cur.execute(
                        """
                        UPDATE support.tickets
                        SET status = %s, assigned_to_user_id = %s::uuid, updated_at = NOW(),
                            closed_at = CASE WHEN %s IN ('resolved','closed') THEN NOW() ELSE closed_at END
                        WHERE id = %s::uuid
                        RETURNING id::text, status, assigned_to_user_id::text
                        """,
                        (status, assigned_to, status, ticket_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE support.tickets
                        SET status = %s, updated_at = NOW(),
                            closed_at = CASE WHEN %s IN ('resolved','closed') THEN NOW() ELSE closed_at END
                        WHERE id = %s::uuid
                        RETURNING id::text, status, assigned_to_user_id::text
                        """,
                        (status, status, ticket_id),
                    )
                row = cur.fetchone()
                conn.commit()
                return dict(row) if row else None

    # --- Activity ---

    def record_activity(self, **kwargs: Any) -> dict[str, Any]:
        if not table_ready("platform", "activity_events"):
            return {}
        event_id = str(uuid4())
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO platform.activity_events (
                        id, org_id, actor_user_id, actor_type, action, entity_type, entity_id,
                        screen_key, feature_code, summary, before_snapshot_id, after_hash,
                        request_id, ip_address, user_agent, metadata
                    ) VALUES (
                        %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s::uuid, %s,
                        %s, %s, %s, %s::jsonb
                    )
                    RETURNING id::text, org_id::text, action, entity_type, entity_id, created_at
                    """,
                    (
                        event_id,
                        kwargs["org_id"],
                        kwargs.get("actor_user_id"),
                        kwargs.get("actor_type") or "user",
                        kwargs["action"],
                        kwargs.get("entity_type"),
                        kwargs.get("entity_id"),
                        kwargs.get("screen_key"),
                        kwargs.get("feature_code"),
                        kwargs.get("summary"),
                        kwargs.get("before_snapshot_id"),
                        kwargs.get("after_hash"),
                        kwargs.get("request_id"),
                        kwargs.get("ip_address"),
                        kwargs.get("user_agent"),
                        Json(kwargs.get("metadata") or {}),
                    ),
                )
                row = dict(cur.fetchone() or {})
                conn.commit()
                return row

    def list_activity(
        self,
        *,
        org_id: str | None = None,
        action: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if not table_ready("platform", "activity_events"):
            return []
        clauses: list[str] = []
        params: list[Any] = []
        if org_id:
            clauses.append("org_id = %s::uuid")
            params.append(org_id)
        if action:
            clauses.append("action = %s")
            params.append(action)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([clamp_limit(limit, maximum=200), clamp_offset(offset)])
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, org_id::text, actor_user_id::text, actor_type, action,
                           entity_type, entity_id, summary, created_at
                    FROM platform.activity_events
                    {where}
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in cur.fetchall()]

    # --- Recycle ---

    def put_recycle(self, **kwargs: Any) -> dict[str, Any]:
        if not table_ready("platform", "recycle_bin"):
            return {}
        rid = str(uuid4())
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO platform.recycle_bin (
                        id, org_id, entity_type, entity_id, snapshot, schema_version,
                        deleted_by, delete_reason, source, restore_status, purge_after,
                        activity_event_id, metadata
                    ) VALUES (
                        %s::uuid, %s::uuid, %s, %s, %s::jsonb, %s, %s::uuid, %s, %s, 'available',
                        NOW() + make_interval(days => %s), %s::uuid, %s::jsonb
                    )
                    RETURNING id::text, org_id::text, entity_type, entity_id, restore_status, deleted_at
                    """,
                    (
                        rid,
                        kwargs["org_id"],
                        kwargs["entity_type"],
                        str(kwargs["entity_id"]),
                        Json(kwargs.get("snapshot") or {}),
                        int(kwargs.get("schema_version") or 1),
                        kwargs.get("deleted_by"),
                        kwargs.get("delete_reason"),
                        kwargs.get("source") or "user",
                        int(kwargs.get("retention_days") or 30),
                        kwargs.get("activity_event_id"),
                        Json(kwargs.get("metadata") or {}),
                    ),
                )
                row = dict(cur.fetchone() or {})
                conn.commit()
                return row

    def list_recycle(
        self, *, org_id: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        if not table_ready("platform", "recycle_bin"):
            return []
        clauses = ["restore_status = 'available'"]
        params: list[Any] = []
        if org_id:
            clauses.append("org_id = %s::uuid")
            params.append(org_id)
        where = "WHERE " + " AND ".join(clauses)
        params.extend([clamp_limit(limit), clamp_offset(offset)])
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, org_id::text, entity_type, entity_id, deleted_by::text,
                           deleted_at, delete_reason, restore_status, purge_after
                    FROM platform.recycle_bin
                    {where}
                    ORDER BY deleted_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in cur.fetchall()]

    def get_recycle(self, recycle_id: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, org_id::text, entity_type, entity_id, snapshot, schema_version,
                           restore_status, deleted_at, deleted_by::text
                    FROM platform.recycle_bin WHERE id = %s::uuid
                    """,
                    (recycle_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def mark_restored(self, recycle_id: str, *, restored_by: str | None) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE platform.recycle_bin
                    SET restore_status = 'restored', restored_at = NOW(), restored_by = %s::uuid
                    WHERE id = %s::uuid AND restore_status = 'available'
                    RETURNING id::text, org_id::text, entity_type, entity_id, restore_status
                    """,
                    (restored_by, recycle_id),
                )
                row = cur.fetchone()
                conn.commit()
                return dict(row) if row else None


control_plane_repository = ControlPlaneRepository()
