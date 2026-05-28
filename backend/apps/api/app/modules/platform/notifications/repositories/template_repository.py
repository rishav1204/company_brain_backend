from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class TemplateRepository:
    def get_template(
        self, org_id: str, *, template_key: str, channel: str
    ) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, template_key, channel, subject_template, body_template, variables
                    FROM notifications.templates
                    WHERE is_active = TRUE AND channel = %s AND template_key = %s
                      AND (org_id = %s::uuid OR org_id IS NULL)
                    ORDER BY org_id NULLS LAST
                    LIMIT 1
                    """,
                    (channel, template_key, org_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list_templates(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, template_key, channel, subject_template, is_active, created_at
                    FROM notifications.templates
                    WHERE org_id = %s::uuid OR org_id IS NULL
                    ORDER BY template_key, channel
                    """,
                    (org_id,),
                )
                return [dict(r) for r in cur.fetchall()]

    def create(
        self,
        org_id: str,
        *,
        template_key: str,
        channel: str,
        body_template: str,
        subject_template: str | None = None,
        variables: list | None = None,
    ) -> dict:
        tid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notifications.templates (
                        id, org_id, template_key, channel, subject_template, body_template, variables
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s::jsonb)
                    RETURNING id::text, template_key, channel
                    """,
                    (
                        tid,
                        org_id,
                        template_key,
                        channel,
                        subject_template,
                        body_template,
                        Json(variables or []),
                    ),
                )
                return dict(cur.fetchone() or {})

    def update(
        self,
        org_id: str,
        template_id: str,
        *,
        subject_template: str | None = None,
        body_template: str | None = None,
        is_active: bool | None = None,
    ) -> dict | None:
        sets: list[str] = []
        params: list[Any] = []
        if subject_template is not None:
            sets.append("subject_template = %s")
            params.append(subject_template)
        if body_template is not None:
            sets.append("body_template = %s")
            params.append(body_template)
        if is_active is not None:
            sets.append("is_active = %s")
            params.append(is_active)
        if not sets:
            return None
        params.extend([template_id, org_id])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE notifications.templates SET {', '.join(sets)}
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    RETURNING id::text, template_key, channel, is_active
                    """,
                    tuple(params),
                )
                row = cur.fetchone()
                return dict(row) if row else None


template_repository = TemplateRepository()
