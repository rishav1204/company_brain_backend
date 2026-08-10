"""Extract APIRouter prefixes + path strings for Wave 0 API manifest."""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

API = Path(__file__).resolve().parents[2] / "backend" / "apps" / "api" / "app"
OUT = Path(__file__).resolve().parent / "_wave0_api_routes.txt"

router_def = re.compile(
    r"(\w+)\s*=\s*APIRouter\s*\(([^)]*)\)",
    re.S,
)
prefix_in = re.compile(r'prefix\s*=\s*["\']([^"\']+)["\']')
# common: @router.get("/foo") or @xxx_router.post(...)
deco = re.compile(
    r"@(\w+)\.(get|post|put|patch|delete|options|head|api_route|websocket)\(\s*[\"']([^\"']*)[\"']"
)

lines_out = []
by_module = defaultdict(list)
total = 0
for p in sorted(API.rglob("*.py")):
    if "test" in str(p).lower():
        continue
    text = p.read_text(encoding="utf-8", errors="ignore")
    rel = str(p.relative_to(API)).replace("\\", "/")
    # map router var -> prefix
    var_prefix: dict[str, str] = {}
    for m in router_def.finditer(text):
        var = m.group(1)
        args = m.group(2)
        pm = prefix_in.search(args)
        var_prefix[var] = pm.group(1) if pm else ""
    # also bare APIRouter() assigned later rare
    for m in deco.finditer(text):
        var, method, path = m.group(1), m.group(2).upper(), m.group(3)
        pref = var_prefix.get(var, "")
        full = (pref.rstrip("/") + "/" + path.lstrip("/")).replace("//", "/") if path else pref
        if not full.startswith("/"):
            full = "/" + full if full else path
        total += 1
        area = rel.split("/")
        owner = "/".join(area[:3]) if area[0] == "modules" else area[0]
        row = f"{method:7} {full:80}  {rel}"
        by_module[owner].append(row)
        lines_out.append(row)

# legacy includes may use router without prefix in file — still capture
OUT.write_text(
    f"# total_with_path_literal={total}\n" + "\n".join(sorted(lines_out)),
    encoding="utf-8",
)
summary = Path(__file__).resolve().parent / "_wave0_api_by_owner.txt"
with summary.open("w", encoding="utf-8") as f:
    for owner, rows in sorted(by_module.items(), key=lambda x: -len(x[1])):
        f.write(f"\n## {owner} ({len(rows)})\n")
        for r in sorted(rows):
            f.write(r + "\n")
print("routes_with_path", total, "owners", len(by_module))
