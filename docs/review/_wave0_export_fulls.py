"""Write supporting full inventories into phase1_wave0/."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INV = Path(__file__).resolve().parent / "_wave0_inventory.json"
OUT = Path(__file__).resolve().parent / "phase1_wave0"
OUT.mkdir(parents=True, exist_ok=True)

d = json.loads(INV.read_text(encoding="utf-8"))


def group(paths: list[str]) -> dict[str, list[str]]:
    g: dict[str, list[str]] = defaultdict(list)
    for s in paths:
        parts = s.split("/")
        if parts[0] == "modules" and len(parts) >= 3:
            key = f"{parts[1]}/{parts[2]}"
        else:
            key = parts[0]
        g[key].append(s)
    return g


def write_grouped(title: str, paths: list[str], name: str) -> None:
    g = group(paths)
    lines = [f"# {title}", f"Total: {len(paths)}", ""]
    for k in sorted(g):
        lines.append(f"## {k} ({len(g[k])})")
        for x in sorted(g[k]):
            lines.append(f"- `{x}`")
        lines.append("")
    (OUT / name).write_text("\n".join(lines), encoding="utf-8")


write_grouped("Service Inventory (filename contains service)", d["service_named"], "_SERVICES_FULL.md")
write_grouped("Repository Inventory (filename contains repositor)", d["repo_named"], "_REPOSITORIES_FULL.md")

(OUT / "_TABLES_FULL.md").write_text(
    (Path(__file__).resolve().parent / "_wave0_tables.md").read_text(encoding="utf-8"),
    encoding="utf-8",
)
(OUT / "_EVENTS_FULL.txt").write_text("\n".join(d["event_type_literals"]), encoding="utf-8")

api_owner = Path(__file__).resolve().parent / "_wave0_api_by_owner.txt"
if api_owner.exists():
    (OUT / "_API_FULL_BY_OWNER.txt").write_text(api_owner.read_text(encoding="utf-8"), encoding="utf-8")

api_sorted = Path(__file__).resolve().parent / "_wave0_api_routes.txt"
if api_sorted.exists():
    (OUT / "_API_FULL_SORTED.txt").write_text(api_sorted.read_text(encoding="utf-8"), encoding="utf-8")

# migrations list
mig = ROOT / "backend" / "migrations"
migs = sorted(p.name for p in mig.glob("*.sql"))
(OUT / "_MIGRATIONS_FULL.txt").write_text("\n".join(migs), encoding="utf-8")

print("ok", OUT)
