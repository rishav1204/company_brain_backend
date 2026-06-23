from __future__ import annotations

import hashlib
from pathlib import Path

from app.core.config import settings
from app.services.db import get_db_conn


def _migrations_dir() -> Path:
    # apps/api/app/services -> repo backend/migrations
    return Path(__file__).resolve().parents[4] / "migrations"


def _checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def migration_status() -> dict:
    """Return pending migration filenames and whether schema is up to date."""
    if not settings.postgres_dsn:
        return {"status": "skipped", "pending": [], "applied_count": 0, "total_count": 0}

    migrations_dir = _migrations_dir()
    if not migrations_dir.is_dir():
        return {"status": "error", "detail": "migrations_dir_missing", "pending": [], "applied_count": 0, "total_count": 0}

    files = sorted(migrations_dir.glob("*.sql"))
    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version TEXT PRIMARY KEY,
                        checksum TEXT NOT NULL,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute("SELECT version, checksum FROM schema_migrations ORDER BY version ASC")
                applied = {str(row["version"]): str(row["checksum"]) for row in (cur.fetchall() or [])}
    except Exception as exc:
        return {
            "status": "error",
            "detail": exc.__class__.__name__,
            "pending": [],
            "applied_count": 0,
            "total_count": len(files),
        }

    pending: list[str] = []
    for migration in files:
        version = migration.name
        content = migration.read_text(encoding="utf-8")
        if version not in applied:
            pending.append(version)
            continue
        if applied[version] != _checksum(content):
            return {
                "status": "error",
                "detail": f"checksum_drift:{version}",
                "pending": pending,
                "applied_count": len(applied),
                "total_count": len(files),
            }

    return {
        "status": "ok" if not pending else "pending",
        "pending": pending,
        "applied_count": len(applied),
        "total_count": len(files),
    }
