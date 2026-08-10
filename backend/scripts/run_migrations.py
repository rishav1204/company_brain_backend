import argparse
import pathlib
import sys

import psycopg

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from migration_utils import applied_versions, checksum, ensure_schema_migrations, is_seed_migration_skipped_in_prod, plan_migrations


def run(dsn: str, migrations_dir: str, dry_run: bool = False) -> int:
    path = pathlib.Path(migrations_dir)
    files = sorted(path.glob("*.sql"))
    if not files:
        print("No migration files found.")
        return 0
    with psycopg.connect(dsn, autocommit=False) as conn:
        with conn.cursor() as cur:
            ensure_schema_migrations(cur)
            applied = applied_versions(cur)
            all_files, pending = plan_migrations(migrations_dir=migrations_dir, applied=applied)
            if dry_run:
                print(f"Applied: {len(applied)} Pending: {len(pending)} Total: {len(all_files)}")
                for migration in pending:
                    print(f"  pending: {migration.name}")
                return 0
            for migration in pending:
                if is_seed_migration_skipped_in_prod(migration.name):
                    print(f"Skipping seed migration in prod: {migration.name}")
                    continue
                sql = migration.read_text(encoding="utf-8")
                version = migration.name
                cur.execute(sql)
                cur.execute(
                    """
                    INSERT INTO schema_migrations (version, checksum, applied_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (version) DO NOTHING
                    """,
                    (version, checksum(sql)),
                )
        conn.commit()
    print(f"Applied {len(pending)} migration(s); total tracked: {len(files)}.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--migrations-dir", default="backend/migrations")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run(dsn=args.dsn, migrations_dir=args.migrations_dir, dry_run=args.dry_run))
