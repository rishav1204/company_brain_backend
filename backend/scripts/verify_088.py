from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "scripts"))
from run_migrations_from_env import load_dsn  # noqa: E402
import psycopg  # noqa: E402


def main() -> None:
    dsn = load_dsn()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM platform.feature_catalog")
            print("features", cur.fetchone()[0])
            cur.execute("SELECT count(*) FROM platform.ui_screen_registry")
            print("screens", cur.fetchone()[0])
            cur.execute("SELECT count(*) FROM platform.org_controls")
            print("org_controls", cur.fetchone()[0])
            cur.execute("SELECT version FROM schema_migrations WHERE version LIKE '088%'")
            print("migration", cur.fetchone())
            cur.execute(
                "SELECT console, count(*) FROM platform.ui_screen_registry GROUP BY console ORDER BY 1"
            )
            print("by_console", cur.fetchall())
            cur.execute(
                "SELECT route_path FROM platform.ui_screen_registry WHERE console = 'platform' ORDER BY sort_order LIMIT 5"
            )
            print("platform_sample", [r[0] for r in cur.fetchall()])


if __name__ == "__main__":
    main()
