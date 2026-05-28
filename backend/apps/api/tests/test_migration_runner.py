import pathlib
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parents[3] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from migration_utils import checksum, plan_migrations


def test_plan_migrations_detects_pending_and_drift(tmp_path) -> None:
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    first = migrations_dir / "001_init.sql"
    first.write_text("CREATE TABLE t1(id INT);", encoding="utf-8")
    applied = {}
    _, pending = plan_migrations(str(migrations_dir), applied)
    assert [item.name for item in pending] == ["001_init.sql"]

    applied["001_init.sql"] = checksum(first.read_text(encoding="utf-8"))
    _, pending = plan_migrations(str(migrations_dir), applied)
    assert pending == []

    first.write_text("CREATE TABLE t1(id INT, name TEXT);", encoding="utf-8")
    try:
        plan_migrations(str(migrations_dir), applied)
        assert False, "Expected checksum drift error"
    except RuntimeError as exc:
        assert "checksum drift" in str(exc)
