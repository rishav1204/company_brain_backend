import hashlib
import os
import pathlib

# DB-26: Dev/demo seed migrations must not run in production
PROD_SKIP_SEED_MIGRATIONS = frozenset({
    "004_benchmark_org_seed.sql",
    "005_tenant_b_seed.sql",
    "020_neon_dev_login.sql",
})


def is_seed_migration_skipped_in_prod(filename: str) -> bool:
    if os.getenv("APP_ENV", "").lower() != "prod":
        return False
    if os.getenv("MIGRATION_ALLOW_SEEDS_IN_PROD", "").lower() == "true":
        return False
    return filename in PROD_SKIP_SEED_MIGRATIONS


def checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def ensure_schema_migrations(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            checksum TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def applied_versions(cur) -> dict[str, str]:
    cur.execute("SELECT version, checksum FROM schema_migrations ORDER BY version ASC")
    return {str(row[0]): str(row[1]) for row in cur.fetchall()}


def plan_migrations(migrations_dir: str, applied: dict[str, str]) -> tuple[list[pathlib.Path], list[pathlib.Path]]:
    path = pathlib.Path(migrations_dir)
    files = sorted(path.glob("*.sql"))
    pending: list[pathlib.Path] = []
    for migration in files:
        version = migration.name
        if is_seed_migration_skipped_in_prod(version):
            continue
        content = migration.read_text(encoding="utf-8")
        if version not in applied:
            pending.append(migration)
            continue
        if applied[version] != checksum(content):
            raise RuntimeError(f"Migration checksum drift detected for {version}")
    return files, pending
