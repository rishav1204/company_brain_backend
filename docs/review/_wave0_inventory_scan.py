"""One-shot inventory scan for Phase 1 Wave 0. Run from repo root or api dir."""
from __future__ import annotations

import re
import json
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
API = REPO / "backend" / "apps" / "api" / "app"
MIG = REPO / "backend" / "migrations"
OUT = Path(__file__).resolve().parent / "_wave0_inventory.json"


def main() -> None:
    data: dict = {}

    # --- files ---
    app_py = list(API.rglob("*.py"))
    data["app_py_count"] = len(app_py)
    data["test_py_count"] = sum(1 for p in app_py if "test" in p.name.lower() or "tests" in p.parts)
    data["service_named"] = sorted(
        str(p.relative_to(API)).replace("\\", "/")
        for p in app_py
        if "service" in p.name.lower() and "test" not in str(p).lower()
    )
    data["repo_named"] = sorted(
        str(p.relative_to(API)).replace("\\", "/")
        for p in app_py
        if "repositor" in p.name.lower() and "test" not in str(p).lower()
    )
    data["worker_named"] = sorted(
        str(p.relative_to(API)).replace("\\", "/")
        for p in app_py
        if ("worker" in p.name.lower() or "/workers/" in str(p).replace("\\", "/"))
        and "test" not in str(p).lower()
    )

    # --- route decorators ---
    route_pat = re.compile(
        r"@(?:router|[a-zA-Z_][\w]*)\.(get|post|put|patch|delete|options|head|api_route|websocket)\("
    )
    prefix_pat = re.compile(r'APIRouter\s*\([^)]*prefix\s*=\s*["\']([^"\']+)["\']')
    routes = []
    for p in app_py:
        if "test" in str(p).lower():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        prefixes = prefix_pat.findall(text)
        for m in route_pat.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            routes.append(
                {
                    "file": str(p.relative_to(API)).replace("\\", "/"),
                    "method": m.group(1).upper(),
                    "line": line,
                    "prefixes_in_file": prefixes,
                }
            )
    data["route_decorator_count"] = len(routes)
    data["route_files"] = sorted({r["file"] for r in routes})
    data["routes_sample"] = routes[:50]

    # count by top folder
    by_top = defaultdict(int)
    for r in routes:
        parts = r["file"].split("/")
        if parts[0] == "modules" and len(parts) > 2:
            by_top[f"modules/{parts[1]}/{parts[2]}"] += 1
        elif parts[0] == "api":
            by_top["api/legacy"] += 1
        else:
            by_top[parts[0]] += 1
    data["routes_by_area"] = dict(sorted(by_top.items(), key=lambda x: -x[1]))

    # --- migrations / tables ---
    tables: set[str] = set()
    table_owner_mig: dict[str, list[str]] = defaultdict(list)
    schemas: set[str] = set()
    for p in sorted(MIG.glob("*.sql")):
        text = p.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_\.\"]+)",
            text,
            re.I,
        ):
            name = m.group(1).replace('"', "")
            tables.add(name)
            table_owner_mig[name].append(p.name)
            if "." in name:
                schemas.add(name.split(".")[0])
        for m in re.finditer(
            r"CREATE\s+SCHEMA\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_]+)",
            text,
            re.I,
        ):
            schemas.add(m.group(1))
    data["migration_count"] = len(list(MIG.glob("*.sql")))
    data["table_count"] = len(tables)
    data["tables"] = sorted(tables)
    data["schemas"] = sorted(schemas)
    data["table_migrations"] = {k: v for k, v in sorted(table_owner_mig.items())}

    # --- event type strings ---
    event_types: set[str] = set()
    et_pat = re.compile(r'event_type\s*=\s*["\']([a-zA-Z0-9_\.\-]+)["\']')
    for p in app_py:
        if "test" in str(p).lower():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for m in et_pat.finditer(text):
            event_types.add(m.group(1))
    data["event_type_literals"] = sorted(event_types)
    data["event_type_count"] = len(event_types)

    # --- stream / queue names ---
    stream_pat = re.compile(r'["\']stream:([a-zA-Z0-9_\.\-]+)["\']')
    queue_pat = re.compile(r'["\']queue:([a-zA-Z0-9_\.\-]+)["\']')
    streams, queues = set(), set()
    for p in app_py:
        text = p.read_text(encoding="utf-8", errors="ignore")
        streams.update(stream_pat.findall(text))
        queues.update(queue_pat.findall(text))
    # also topology.py freestyle names
    data["streams_literal"] = sorted(streams)
    data["queues_literal"] = sorted(queues)

    # --- cross-layer imports ---
    fos_imports_erp = []
    erp_imports_fos = []
    for p in app_py:
        if "test" in str(p).lower():
            continue
        rel = str(p.relative_to(API)).replace("\\", "/")
        text = p.read_text(encoding="utf-8", errors="ignore")
        if "modules/finance_os" in rel:
            hits = re.findall(r"from app\.modules\.erp\.[\w\.]+|import app\.modules\.erp", text)
            if hits or "modules.erp" in text:
                imps = re.findall(r"from (app\.modules\.erp\.[\w.]+) import", text)
                imps += re.findall(r"import (app\.modules\.erp\.[\w.]+)", text)
                if imps:
                    fos_imports_erp.append({"file": rel, "imports": sorted(set(imps))})
        if "modules/erp" in rel:
            imps = re.findall(r"from (app\.modules\.finance_os\.[\w.]+) import", text)
            imps += re.findall(r"import (app\.modules\.finance_os\.[\w.]+)", text)
            if imps:
                erp_imports_fos.append({"file": rel, "imports": sorted(set(imps))})
    data["fos_imports_erp"] = fos_imports_erp
    data["erp_imports_fos"] = erp_imports_fos

    # --- module package tree ---
    modules = API / "modules"
    tree: dict = {}
    for top in sorted(modules.iterdir()):
        if not top.is_dir() or top.name.startswith("."):
            continue
        tree[top.name] = {}
        for sub in sorted(top.iterdir()):
            if not sub.is_dir() or sub.name == "__pycache__":
                continue
            py_n = len(list(sub.rglob("*.py")))
            tree[top.name][sub.name] = {"py_files": py_n}
    data["module_tree"] = tree

    # --- settings field names ---
    cfg = API / "core" / "config.py"
    if cfg.exists():
        ct = cfg.read_text(encoding="utf-8", errors="ignore")
        fields = re.findall(r"^    ([a-z][a-z0-9_]*)\s*:", ct, re.M)
        data["settings_fields"] = fields
        data["settings_field_count"] = len(fields)

    # --- routers in main ---
    main = API / "main.py"
    mt = main.read_text(encoding="utf-8", errors="ignore")
    data["main_include_router_count"] = len(re.findall(r"include_router\(", mt))
    data["main_middleware"] = re.findall(r"add_middleware\((\w+)", mt)

    OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("wrote", OUT)
    print("tables", data["table_count"], "routes", data["route_decorator_count"])
    print("events", data["event_type_count"], "services", len(data["service_named"]))
    print("repos", len(data["repo_named"]), "workers", len(data["worker_named"]))
    print("fos->erp files", len(fos_imports_erp), "erp->fos files", len(erp_imports_fos))


if __name__ == "__main__":
    main()
