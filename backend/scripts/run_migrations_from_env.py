"""Apply pending migrations using POSTGRES_DSN from backend/apps/api/.env."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / "backend" / "apps" / "api" / ".env"
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_migrations import run  # noqa: E402


def load_dsn() -> str:
    if not ENV_PATH.is_file():
        raise SystemExit(f"Missing env file: {ENV_PATH}")
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("POSTGRES_DSN="):
            value = line.split("=", 1)[1].strip()
            if value and "USER:PASSWORD" not in value:
                return value
    raise SystemExit("POSTGRES_DSN not set in backend/apps/api/.env")


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    dsn = load_dsn()
    migrations_dir = str(ROOT / "backend" / "migrations")
    if dry_run:
        print("Dry-run: listing pending migrations...")
        return run(dsn=dsn, migrations_dir=migrations_dir, dry_run=True)
    print("Applying pending migrations...")
    return run(dsn=dsn, migrations_dir=migrations_dir, dry_run=False)


if __name__ == "__main__":
    raise SystemExit(main())
