import argparse
import pathlib
import sys

import psycopg

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from migration_utils import applied_versions, ensure_schema_migrations, plan_migrations


def run(dsn: str, migrations_dir: str) -> int:
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            ensure_schema_migrations(cur)
            applied = applied_versions(cur)
    all_files, pending = plan_migrations(migrations_dir=migrations_dir, applied=applied)
    print(f"applied={len(applied)} pending={len(pending)} total={len(all_files)}")
    for migration in all_files:
        state = "applied" if migration.name in applied else "pending"
        print(f"{migration.name}\t{state}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--migrations-dir", default="backend/migrations")
    args = parser.parse_args()
    raise SystemExit(run(dsn=args.dsn, migrations_dir=args.migrations_dir))
