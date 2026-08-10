from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from psycopg.types.json import Json

from app.core.config import settings
from app.services.db import get_db_conn, set_rls_org


# Outbox lifecycle (Wave 2)
OUTBOX_PENDING = "pending"
OUTBOX_PUBLISHING = "publishing"
OUTBOX_PUBLISHED = "published"
OUTBOX_FAILED = "failed"
OUTBOX_DEAD = "dead"
OUTBOX_ARCHIVED = "archived"


@dataclass(frozen=True)
class OutboxRow:
    id: str
    org_id: str
    event_id: str
    queue_name: str
    envelope: dict
    attempt_count: int


def _payload_checksum(envelope: dict) -> str:
    raw = json.dumps(envelope or {}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class OutboxRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'platform' AND table_name = 'event_outbox'
                        LIMIT 1
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def wave2_columns_ready(self, conn=None) -> bool:
        """True when migration 085 metadata columns exist."""

        def _check(c) -> bool:
            with c.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'platform'
                      AND table_name = 'event_outbox'
                      AND column_name = 'payload_checksum'
                    LIMIT 1
                    """
                )
                return cur.fetchone() is not None

        if conn is not None:
            try:
                return _check(conn)
            except Exception:
                return False
        try:
            with get_db_conn() as c:
                return _check(c)
        except Exception:
            return False

    def enqueue_with_conn(
        self,
        conn,
        *,
        org_id: str,
        event_id: str,
        queue_name: str,
        envelope: dict,
        event_type: str | None = None,
        event_version: str | None = None,
        correlation_id: str | None = None,
        request_id: str | None = None,
        company_id: str | None = None,
        actor_id: str | None = None,
        partition_key: str | None = None,
        ordering_key: str | None = None,
        is_financial: bool = False,
    ) -> None:
        set_rls_org(conn, org_id)
        env = envelope if isinstance(envelope, dict) else {}
        et = event_type or str(env.get("event_type") or "")
        ev = event_version or str(env.get("schema_version") or env.get("event_version") or "v1")
        checksum = _payload_checksum(env)
        wave2 = self.wave2_columns_ready(conn)
        with conn.cursor() as cur:
            if wave2:
                cur.execute(
                    """
                    INSERT INTO platform.event_outbox (
                        org_id, event_id, queue_name, envelope, status,
                        event_type, event_version, correlation_id, request_id,
                        company_id, actor_id, partition_key, ordering_key,
                        payload_checksum, is_financial
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s, %s::jsonb, 'pending',
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s
                    )
                    ON CONFLICT (org_id, event_id) DO NOTHING
                    """,
                    (
                        org_id,
                        event_id,
                        queue_name,
                        Json(env),
                        et or None,
                        ev,
                        correlation_id,
                        request_id,
                        company_id if company_id else None,
                        actor_id,
                        partition_key,
                        ordering_key,
                        checksum,
                        bool(is_financial),
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO platform.event_outbox (org_id, event_id, queue_name, envelope, status)
                    VALUES (%s::uuid, %s::uuid, %s, %s::jsonb, 'pending')
                    ON CONFLICT (org_id, event_id) DO NOTHING
                    """,
                    (org_id, event_id, queue_name, Json(env)),
                )

    def reenqueue_for_replay_with_conn(
        self,
        conn,
        *,
        org_id: str,
        event_id: str,
        queue_name: str,
        envelope: dict,
        **meta: Any,
    ) -> None:
        """Operator replay: insert outbox row with new event_id expected in envelope."""
        self.enqueue_with_conn(
            conn,
            org_id=org_id,
            event_id=event_id,
            queue_name=queue_name,
            envelope=envelope,
            event_type=meta.get("event_type"),
            event_version=meta.get("event_version"),
            correlation_id=meta.get("correlation_id"),
            request_id=meta.get("request_id"),
            company_id=meta.get("company_id"),
            actor_id=meta.get("actor_id"),
            partition_key=meta.get("partition_key"),
            ordering_key=meta.get("ordering_key"),
            is_financial=bool(meta.get("is_financial")),
        )

    def claim_batch(
        self,
        *,
        publisher_id: str,
        limit: int = 50,
        lock_seconds: int = 30,
    ) -> list[OutboxRow]:
        """
        Claim outbox rows without relying on Redis for correctness.
        Uses a lease in Postgres (locked_until) to allow crash recovery.
        """
        limit = max(1, min(int(limit or 50), 500))
        lock_seconds = max(5, min(int(lock_seconds or 30), 300))
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH picked AS (
                        SELECT id
                        FROM platform.event_outbox
                        WHERE status IN ('pending','failed')
                          AND (next_attempt_at IS NULL OR next_attempt_at <= now())
                          AND (locked_until IS NULL OR locked_until < now())
                        ORDER BY created_at ASC
                        LIMIT %s
                        FOR UPDATE SKIP LOCKED
                    )
                    UPDATE platform.event_outbox o
                    SET status = 'publishing',
                        locked_by = %s,
                        locked_until = now() + (%s || ' seconds')::interval,
                        updated_at = now()
                    FROM picked
                    WHERE o.id = picked.id
                    RETURNING o.id::text, o.org_id::text, o.event_id::text, o.queue_name,
                              o.envelope, o.attempt_count
                    """,
                    (limit, publisher_id, str(lock_seconds)),
                )
                rows = cur.fetchall() or []
                out: list[OutboxRow] = []
                for r in rows:
                    d = dict(r) if isinstance(r, dict) else r
                    out.append(
                        OutboxRow(
                            id=str(d["id"]),
                            org_id=str(d["org_id"]),
                            event_id=str(d["event_id"]),
                            queue_name=str(d["queue_name"]),
                            envelope=d.get("envelope") if isinstance(d.get("envelope"), dict) else {},
                            attempt_count=int(d.get("attempt_count") or 0),
                        )
                    )
                conn.commit()
                return out

    def mark_published(self, *, org_id: str, outbox_id: str, redis_stream_id: str | None) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE platform.event_outbox
                    SET status = 'published',
                        published_at = now(),
                        redis_stream_id = %s,
                        locked_until = NULL,
                        updated_at = now()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (redis_stream_id, org_id, outbox_id),
                )
            conn.commit()

    def mark_failed(
        self,
        *,
        org_id: str,
        outbox_id: str,
        error: str,
        next_attempt_at: str | None,
        attempt_count: int | None = None,
        failure_class: str | None = None,
    ) -> str:
        """
        Increment attempts; promote to dead when over OUTBOX_MAX_ATTEMPTS.
        Returns new status ('failed' or 'dead').
        """
        max_attempts = max(1, int(getattr(settings, "outbox_max_attempts", 10) or 10))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            wave2 = self.wave2_columns_ready(conn)
            with conn.cursor() as cur:
                if wave2:
                    cur.execute(
                        """
                        UPDATE platform.event_outbox
                        SET attempt_count = attempt_count + 1,
                            last_error = %s,
                            failure_class = COALESCE(%s, failure_class),
                            next_attempt_at = CASE
                                WHEN attempt_count + 1 >= %s THEN NULL
                                ELSE COALESCE(%s::timestamptz, next_attempt_at)
                            END,
                            status = CASE
                                WHEN attempt_count + 1 >= %s THEN 'dead'
                                ELSE 'failed'
                            END,
                            dead_at = CASE
                                WHEN attempt_count + 1 >= %s THEN now()
                                ELSE dead_at
                            END,
                            locked_until = NULL,
                            updated_at = now()
                        WHERE org_id = %s::uuid AND id = %s::uuid
                        RETURNING status
                        """,
                        (
                            error[:1000],
                            failure_class,
                            max_attempts,
                            next_attempt_at,
                            max_attempts,
                            max_attempts,
                            org_id,
                            outbox_id,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE platform.event_outbox
                        SET status = 'failed',
                            attempt_count = attempt_count + 1,
                            last_error = %s,
                            next_attempt_at = COALESCE(%s::timestamptz, next_attempt_at),
                            locked_until = NULL,
                            updated_at = now()
                        WHERE org_id = %s::uuid AND id = %s::uuid
                        RETURNING status
                        """,
                        (error[:1000], next_attempt_at, org_id, outbox_id),
                    )
                row = cur.fetchone()
            conn.commit()
        if not row:
            return OUTBOX_FAILED
        status = str(row["status"] if isinstance(row, dict) else row[0])
        return status

    def mark_dead(
        self,
        *,
        org_id: str,
        outbox_id: str,
        error: str,
        failure_class: str = "operator",
    ) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            wave2 = self.wave2_columns_ready(conn)
            with conn.cursor() as cur:
                if wave2:
                    cur.execute(
                        """
                        UPDATE platform.event_outbox
                        SET status = 'dead',
                            last_error = %s,
                            failure_class = %s,
                            dead_at = now(),
                            locked_until = NULL,
                            next_attempt_at = NULL,
                            updated_at = now()
                        WHERE org_id = %s::uuid AND id = %s::uuid
                        """,
                        (error[:1000], failure_class, org_id, outbox_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE platform.event_outbox
                        SET status = 'failed',
                            last_error = %s,
                            locked_until = NULL,
                            updated_at = now()
                        WHERE org_id = %s::uuid AND id = %s::uuid
                        """,
                        (error[:1000], org_id, outbox_id),
                    )
            conn.commit()

    def resurrect_dead(
        self,
        *,
        org_id: str,
        outbox_id: str,
    ) -> None:
        """Operator recovery: dead → pending for republish."""
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE platform.event_outbox
                    SET status = 'pending',
                        next_attempt_at = now(),
                        locked_until = NULL,
                        locked_by = NULL,
                        updated_at = now()
                    WHERE org_id = %s::uuid AND id = %s::uuid AND status = 'dead'
                    """,
                    (org_id, outbox_id),
                )
            conn.commit()

    def stats(self) -> dict[str, int]:
        """Global publisher metrics (cross-tenant; ops worker only)."""
        if not self.schema_ready():
            return {}
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT status, count(*)::int AS c
                        FROM platform.event_outbox
                        GROUP BY status
                        """
                    )
                    rows = cur.fetchall() or []
            out: dict[str, int] = {}
            for r in rows:
                d = dict(r) if isinstance(r, dict) else {"status": r[0], "c": r[1]}
                out[str(d["status"])] = int(d["c"])
            return out
        except Exception:
            return {}

    def archive_published(self, *, older_than_days: int | None = None) -> int:
        days = int(older_than_days or getattr(settings, "outbox_archive_after_days", 90) or 90)
        if not self.schema_ready() or not self.wave2_columns_ready():
            return 0
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE platform.event_outbox
                        SET status = 'archived',
                            archived_at = now(),
                            updated_at = now()
                        WHERE status = 'published'
                          AND published_at IS NOT NULL
                          AND published_at < now() - (%s || ' days')::interval
                        """,
                        (str(days),),
                    )
                    n = cur.rowcount or 0
                conn.commit()
                return int(n)
        except Exception:
            return 0


outbox_repository = OutboxRepository()
