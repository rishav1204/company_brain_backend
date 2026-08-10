"""Generate platform.ui_screen_registry seed SQL from FE nav-config.ts."""
from __future__ import annotations

import re
from pathlib import Path

NAV = Path(r"D:\new-project-fe\apps\web\src\config\nav-config.ts")
MIGRATION = Path(r"D:\new_project\backend\migrations\088_platform_control_plane.sql")

# path prefix/exact → feature_code
FEATURE_RULES: list[tuple[str, str | None]] = [
    ("/intelligence/invoice-ai", "invoice_ai"),
    ("/intelligence/workflow", "workflow_intelligence"),
    ("/intelligence/agents", "agents"),
    ("/intelligence/memory", "memory"),
    ("/intelligence/graph", "graph_engine"),
    ("/intelligence/forecasting", "forecasting"),
    ("/accounting/coa", "coa"),
    ("/accounting/journals", "journals"),
    ("/accounting/gl", "gl"),
    ("/accounting/vouchers", "vouchers"),
    ("/accounting/fiscal", "gl"),
    ("/operations/ap", "ap"),
    ("/operations/ar", "ar"),
    ("/operations/procurement", "procurement"),
    ("/operations/expenses", "expense"),
    ("/operations/assets", "assets"),
    ("/operations/inventory", "inventory"),
    ("/compliance/gst", "gst"),
    ("/compliance/tds", "tds"),
    ("/compliance", "compliance"),
    ("/treasury/banking", "banking"),
    ("/treasury/reconciliation", "reconciliation"),
    ("/treasury", "treasury"),
    ("/reports", "reporting"),
    ("/governance/audit", "audit_explorer"),
    ("/governance/violations", "audit_explorer"),
]


def screen_key_for(path: str, console: str) -> str:
    parts = [p for p in path.strip("/").split("/") if p]
    # Avoid admin.admin.* / platform.platform.* when path already starts with console name
    if parts and parts[0] in {"admin", "platform", "workspace"}:
        if console in {parts[0], "admin", "platform"}:
            parts = parts[1:]
    if not parts:
        return f"{console}.root"
    cleaned = []
    for p in parts:
        cleaned.append(re.sub(r"[^a-zA-Z0-9]+", "_", p).strip("_").lower())
    return f"{console}." + ".".join(cleaned)


def feature_for(path: str) -> str | None:
    for prefix, code in FEATURE_RULES:
        if path == prefix or path.startswith(prefix + "/"):
            return code
    return None


def console_for(path: str) -> str:
    if path.startswith("/admin/"):
        return "admin"
    if path.startswith("/platform"):
        return "platform"
    return "erp"


def sql_escape(s: str) -> str:
    return s.replace("'", "''")


def parse_nav_items(text: str) -> list[dict]:
    # Match { label: "...", href: "...", permission?: "...", featureCode?: "..." }
    items = []
    current_cat = None
    for line in text.splitlines():
        mcat = re.search(r'label:\s*"([^"]+)"\s*,\s*\n?\s*icon:', line)
        # simpler: track category by `label: "X",` right after NAV_CONFIG blocks — use icon lines
        if re.search(r'icon:\s*"', line):
            # previous non-icon label is category — fallback: parse full file with state
            pass
    # dual pass with block state
    cat = "General"
    for line in text.splitlines():
        cl = re.search(r'^\s*label:\s*"([^"]+)"\s*,\s*$', line)
        ic = re.search(r'icon:\s*"', line)
        # if line after category starts with icon key inside NAV category objects
        if "icon:" in line and "NavIconKey" not in line:
            # lookback - we store pending label
            pass
    # Robust: extract all href items with nearby label + permission + featureCode
    pattern = re.compile(
        r'\{\s*label:\s*"(?P<label>[^"]+)"\s*,\s*href:\s*"(?P<href>[^"]+)"'
        r'(?:\s*,\s*permission:\s*"(?P<perm>[^"]*)")?'
        r'(?:\s*,\s*featureCode:\s*"(?P<feat>[^"]*)")?\s*,?\s*\}',
        re.M,
    )
    # Also multi-line objects for notification templates
    pattern2 = re.compile(
        r'label:\s*"(?P<label>[^"]+)"\s*,\s*\n\s*href:\s*"(?P<href>[^"]+)"\s*,\s*\n\s*permission:\s*"(?P<perm>[^"]+)"',
        re.M,
    )

    # Category attribution by walking
    for m in pattern.finditer(text):
        items.append(
            {
                "label": m.group("label"),
                "href": m.group("href"),
                "permission": m.group("perm"),
                "feature": m.group("feat"),
            }
        )
    for m in pattern2.finditer(text):
        href = m.group("href")
        if any(i["href"] == href for i in items):
            continue
        items.append(
            {
                "label": m.group("label"),
                "href": href,
                "permission": m.group("perm"),
                "feature": None,
            }
        )
    return items


def category_for(path: str) -> str:
    if path.startswith("/accounting"):
        return "Accounting"
    if path.startswith("/operations"):
        return "Operations"
    if path.startswith("/compliance"):
        return "Compliance"
    if path.startswith("/treasury"):
        return "Treasury"
    if path.startswith("/intelligence"):
        return "Intelligence"
    if path.startswith("/reports"):
        return "Reporting"
    if path.startswith("/governance"):
        return "Governance"
    if path.startswith("/admin"):
        return "Administration"
    if path.startswith("/workflows") or path in {"/dashboard", "/notifications"} or path.startswith("/documents"):
        return "Finance"
    if path.startswith("/platform"):
        return "Platform"
    if path.startswith("/support"):
        return "Administration"
    return "General"


def build_rows() -> list[dict]:
    text = NAV.read_text(encoding="utf-8")
    nav_items = parse_nav_items(text)
    rows: list[dict] = []
    seen: set[str] = set()

    def add(href: str, label: str, permission: str | None, feature: str | None = None, console: str | None = None):
        console = console or console_for(href)
        sk = screen_key_for(href, console)
        if sk in seen:
            return
        seen.add(sk)
        feat = feature if feature is not None else feature_for(href)
        rows.append(
            {
                "screen_key": sk,
                "route_path": href,
                "label": label,
                "nav_category": category_for(href),
                "feature_code": feat,
                "permission_key": permission,
                "console": console,
                "sort_order": (len(rows) + 1) * 10,
            }
        )

    for it in nav_items:
        add(it["href"], it["label"], it["permission"], it["feature"])

    # Platform owner console (not in NAV_CONFIG)
    for href, label in [
        ("/platform", "Platform overview"),
        ("/platform/orgs", "Organizations"),
        ("/platform/users", "Users"),
        ("/platform/usage", "Usage"),
        ("/platform/commercial", "Commercial"),
        ("/platform/features", "Features"),
        ("/platform/support", "Platform support"),
        ("/platform/activity", "Platform activity"),
        ("/platform/recycle-bin", "Platform recycle bin"),
        ("/platform/ops/queues", "Queues"),
        ("/platform/ops/jobs", "Jobs"),
        ("/platform/ops/events", "Events"),
        ("/platform/ops/workers", "Workers"),
        ("/platform/ops/webhook-deliveries", "Webhook deliveries"),
        ("/platform/observability", "Observability"),
        ("/platform/ai", "AI ops"),
    ]:
        add(href, label, "platform.admin", None, "platform")

    return rows


def sql_value(v: str | None) -> str:
    if v is None:
        return "NULL"
    return f"'{sql_escape(v)}'"


def generate_insert(rows: list[dict]) -> str:
    lines = [
        "INSERT INTO platform.ui_screen_registry",
        "    (screen_key, route_path, label, nav_category, feature_code, permission_key, console, sort_order)",
        "VALUES",
    ]
    value_lines = []
    for r in rows:
        value_lines.append(
            "    ({sk}, {rp}, {lb}, {nc}, {fc}, {pk}, {cn}, {so})".format(
                sk=sql_value(r["screen_key"]),
                rp=sql_value(r["route_path"]),
                lb=sql_value(r["label"]),
                nc=sql_value(r["nav_category"]),
                fc=sql_value(r["feature_code"]),
                pk=sql_value(r["permission_key"]),
                cn=sql_value(r["console"]),
                so=r["sort_order"],
            )
        )
    lines.append(",\n".join(value_lines))
    lines.append("ON CONFLICT (screen_key) DO UPDATE SET")
    lines.append("    route_path = EXCLUDED.route_path,")
    lines.append("    label = EXCLUDED.label,")
    lines.append("    nav_category = EXCLUDED.nav_category,")
    lines.append("    feature_code = EXCLUDED.feature_code,")
    lines.append("    permission_key = EXCLUDED.permission_key,")
    lines.append("    console = EXCLUDED.console,")
    lines.append("    sort_order = EXCLUDED.sort_order,")
    lines.append("    status = 'active',")
    lines.append("    updated_at = NOW();")
    return "\n".join(lines)


def main() -> None:
    rows = build_rows()
    insert_sql = generate_insert(rows)
    text = MIGRATION.read_text(encoding="utf-8")

    # Ensure inventory feature in catalog
    if "('inventory'," not in text and "('inventory', " not in text:
        text = text.replace(
            "('multi_entity', 'Multi-entity', 'erp', FALSE)\nON CONFLICT (feature_code) DO NOTHING;",
            "('multi_entity', 'Multi-entity', 'erp', FALSE),\n"
            "    ('inventory', 'Inventory', 'erp', FALSE)\n"
            "ON CONFLICT (feature_code) DO NOTHING;",
        )

    start = text.find("-- Seed key screens from product NAV")
    if start < 0:
        start = text.find("INSERT INTO platform.ui_screen_registry")
    end = text.find("-- ---------------------------------------------------------------------------\n-- Org / user controls", start)
    if start < 0 or end < 0:
        raise SystemExit("could not locate screen seed block in migration")

    new_block = (
        "-- Seed screens from FE NAV_CONFIG + platform owner console (idempotent upsert)\n"
        f"{insert_sql}\n\n"
    )
    text = text[:start] + new_block + text[end:]
    MIGRATION.write_text(text, encoding="utf-8")
    print(f"seeded {len(rows)} screens into migration")
    # also dump a quick check file
    out = Path(r"D:\new_project\backend\scripts\_screen_seed_preview.txt")
    out.write_text("\n".join(f"{r['screen_key']}\t{r['route_path']}\t{r['feature_code']}" for r in rows), encoding="utf-8")
    print("preview", out)


if __name__ == "__main__":
    main()
