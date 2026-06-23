#!/usr/bin/env python3
"""Implementation completeness audit — inventories, stubs, quality metrics, module scores."""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "apps" / "api" / "app"
MIGRATIONS = REPO / "migrations"
OUT_JSON = REPO / "ENTERPRISE_CODE_QUALITY_REVIEW_DATA.json"
OUT_MD = REPO / "ENTERPRISE_CODE_QUALITY_REVIEW.md"

# M01–M37 module path mapping
MODULE_MAP: dict[str, dict] = {
    "M01": {"name": "IAM", "path": "modules/core/iam", "migration": ["009", "010", "011"]},
    "M02": {"name": "Workflow Engine", "path": "modules/workflows", "migration": ["012", "013", "014"]},
    "M03": {"name": "Event Bus", "path": "modules/platform/events", "migration": ["015"]},
    "M04": {"name": "Audit Core", "path": "modules/platform/governance", "migration": ["016", "017"]},
    "M05": {"name": "Notifications", "path": "modules/platform/notifications", "migration": ["018", "019"]},
    "M06": {"name": "Documents", "path": "modules/platform/documents", "migration": ["021"]},
    "M07": {"name": "Integrations", "path": "modules/platform/integrations", "migration": ["027"]},
    "M08": {"name": "Chart of Accounts", "path": "modules/erp/coa", "migration": ["028", "029"]},
    "M09": {"name": "General Ledger", "path": "modules/erp/gl", "migration": ["030"]},
    "M10": {"name": "Journal Engine", "path": "modules/erp/journals", "migration": ["031", "032"]},
    "M11": {"name": "Voucher Engine", "path": "modules/erp/vouchers", "migration": ["062", "064"]},
    "M12": {"name": "Fiscal Periods", "path": "modules/erp/fiscal", "migration": ["039"]},
    "M13": {"name": "Accounts Payable", "path": "modules/erp/accounts_payable", "migration": ["033", "063"]},
    "M14": {"name": "Accounts Receivable", "path": "modules/erp/accounts_receivable", "migration": ["034"]},
    "M15": {"name": "Procurement", "path": "modules/erp/procurement", "migration": ["040"]},
    "M16": {"name": "Expense Management", "path": "modules/erp/expenses", "migration": ["041"]},
    "M17": {"name": "Fixed Assets", "path": "modules/erp/assets", "migration": ["042"]},
    "M18": {"name": "Inventory", "path": "modules/erp/inventory", "migration": ["043"]},
    "M19": {"name": "GST Engine", "path": "modules/erp/tax", "migration": ["036"]},
    "M20": {"name": "TDS/TCS Engine", "path": "modules/erp/tax", "migration": ["044", "045"]},
    "M21": {"name": "Compliance Calendar", "path": "modules/erp/compliance", "migration": ["046"]},
    "M22": {"name": "Banking", "path": "modules/erp/banking", "migration": ["047"]},
    "M23": {"name": "Reconciliation", "path": "modules/erp/reconciliation", "migration": ["048"]},
    "M24": {"name": "Treasury", "path": "modules/erp/treasury", "migration": ["035", "049"]},
    "M25": {"name": "AI Invoice Intelligence", "path": "modules/finance_os/invoice_ai", "migration": ["050"]},
    "M26": {"name": "Workflow Intelligence", "path": "modules/finance_os/workflow_intelligence", "migration": ["051"]},
    "M27": {"name": "Memory System", "path": "modules/finance_os/memory", "migration": ["052"]},
    "M28": {"name": "Graph Engine", "path": "modules/finance_os/graph", "migration": ["053"]},
    "M29": {"name": "AI Agents", "path": "modules/finance_os/agents", "migration": ["054"]},
    "M30": {"name": "Forecasting", "path": "modules/finance_os/forecasting", "migration": ["055"]},
    "M31": {"name": "Reporting", "path": "modules/erp/reporting", "migration": ["056"]},
    "M32": {"name": "Analytics & BI", "path": "modules/finance_os/analytics", "migration": ["057"]},
    "M33": {"name": "Audit Explorer", "path": "modules/finance_os/audit_explorer", "migration": ["058"]},
    "M34": {"name": "Policy Engine", "path": "modules/platform/governance", "migration": ["059"]},
    "M35": {"name": "Consolidation", "path": "modules/erp/consolidation", "migration": ["060"]},
    "M36": {"name": "API Gateway", "path": "modules/platform/api_gateway", "migration": ["061"]},
    "M37": {"name": "Billing", "path": "modules/platform/billing", "migration": ["065"]},
}

STUB_PATTERNS = [
    (re.compile(r"\bstub\b", re.I), "stub_keyword"),
    (re.compile(r"\bplaceholder\b", re.I), "placeholder"),
    (re.compile(r"not_implemented", re.I), "not_implemented"),
    (re.compile(r'"model"\s*:\s*"stub"', re.I), "stub_model"),
    (re.compile(r"for now", re.I), "for_now"),
]

CRITICAL_STUB_FILES = {
    "modules/platform/notifications/providers/push_provider.py",
    "modules/platform/notifications/providers/sms_provider.py",
    "modules/platform/documents/workers/thumbnail_worker.py",
    "modules/platform/documents/ai/gst_extractor.py",
    "modules/platform/documents/providers/s3_provider.py",
}

LEGITIMATE_NOT_IMPLEMENTED = {
    "modules/finance_os/agents/agents/base_agent.py",
    "modules/erp/vouchers/generators/base_generator.py",
}


def _rel(py: Path) -> str:
    return str(py.relative_to(APP)).replace("\\", "/")


def _is_test(py: Path) -> bool:
    rel = _rel(py)
    return "/tests/" in rel or rel.startswith("tests/")


def scan_inventories() -> dict:
    inv: dict[str, list[str]] = defaultdict(list)
    for py in sorted(APP.rglob("*.py")):
        rel = _rel(py)
        inv["all_python"].append(rel)
        if _is_test(py):
            inv["tests"].append(rel)
        if "/services/" in rel and not rel.endswith("__init__.py"):
            inv["services"].append(rel)
        if "/routes/" in rel and rel.endswith(".py"):
            inv["routes"].append(rel)
        if "/repositories/" in rel and rel.endswith(".py"):
            inv["repositories"].append(rel)
        if "/models/" in rel and rel.endswith(".py"):
            inv["models"].append(rel)
        if "/read_models/" in rel and rel.endswith(".py"):
            inv["read_models"].append(rel)
        if "/schemas/" in rel and rel.endswith(".py"):
            inv["schemas"].append(rel)
        if "/workers/" in rel and rel.endswith(".py"):
            inv["workers"].append(rel)
        if "/pipelines/" in rel and rel.endswith(".py"):
            inv["pipelines"].append(rel)
        if rel.startswith("api/routes/"):
            inv["legacy_routes"].append(rel)
        if rel.startswith("services/") and "/services/" not in rel[9:]:
            inv["legacy_services"].append(rel)
    return {k: sorted(v) for k, v in inv.items()}


def scan_stubs() -> dict:
    findings: list[dict] = []
    for py in APP.rglob("*.py"):
        if _is_test(py):
            continue
        rel = _rel(py)
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            for pat, kind in STUB_PATTERNS:
                if pat.search(line):
                    findings.append({"file": rel, "line": line_no, "kind": kind, "snippet": line.strip()[:120]})
    critical = [f for f in findings if f["file"] in CRITICAL_STUB_FILES]
    return {"all": findings, "critical_count": len({f["file"] for f in critical}), "critical": critical}


def scan_code_quality() -> dict:
    large_files: list[dict] = []
    long_funcs: list[dict] = []
    silent_excepts: list[dict] = []
    for py in APP.rglob("*.py"):
        if _is_test(py):
            continue
        rel = _rel(py)
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
            lines = len(text.splitlines())
        except OSError:
            continue
        if lines > 500:
            large_files.append({"file": rel, "lines": lines})
        for line_no, line in enumerate(text.splitlines(), 1):
            if re.match(r"\s*except\s+Exception\s*:\s*pass\s*$", line):
                silent_excepts.append({"file": rel, "line": line_no})
        try:
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    end = getattr(node, "end_lineno", node.lineno) or node.lineno
                    flen = end - node.lineno + 1
                    if flen > 100:
                        long_funcs.append({"file": rel, "line": node.lineno, "name": node.name, "lines": flen})
        except SyntaxError:
            pass
    large_files.sort(key=lambda x: -x["lines"])
    long_funcs.sort(key=lambda x: -x["lines"])
    return {
        "large_files": large_files[:30],
        "long_functions": long_funcs[:30],
        "silent_except_exception_pass": silent_excepts,
        "silent_except_count": len(silent_excepts),
    }


def scan_unbounded_fetchall() -> list[str]:
    hits: list[str] = []
    for py in APP.rglob("**/repositories/*.py"):
        rel = _rel(py)
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "fetchall()" not in text:
            continue
        for match in re.finditer(r"cur\.execute\(", text):
            start = match.start()
            snippet_after = text[start : start + 1500]
            if "fetchall()" not in snippet_after:
                continue
            context = text[max(0, start - 2500) : start + 1500]
            upper = context.upper()
            if "LIMIT %S" in upper or re.search(r"LIMIT\s+1\b", upper):
                continue
            if re.search(r"limit\s*=\s*max\(", context) or "params.append(limit)" in context:
                continue
            hits.append(f"{rel}: unbounded fetchall")
            break
    return list(dict.fromkeys(hits))


def _module_files(module_path: str) -> list[Path]:
    base = APP / module_path.replace("/", "\\") if "\\" in str(APP) else APP / module_path
    if not base.exists():
        return []
    return list(base.rglob("*.py"))


def _has_migration(prefixes: list[str]) -> bool:
    for sql in MIGRATIONS.glob("*.sql"):
        name = sql.name
        for p in prefixes:
            if name.startswith(p + "_") or p in name:
                return True
    return False


def score_modules(stubs: dict, unbounded: list[str]) -> dict:
    stub_files = {f["file"] for f in stubs["all"]}
    scores: dict[str, dict] = {}
    for mid, meta in MODULE_MAP.items():
        path = meta["path"]
        files = _module_files(path)
        non_test = [f for f in files if not _is_test(f)]
        services = [f for f in non_test if "/services/" in _rel(f)]
        routes = [f for f in non_test if "/routes/" in _rel(f)]
        repos = [f for f in non_test if "/repositories/" in _rel(f)]
        tests = [f for f in files if _is_test(f)]
        module_stub = [s for s in stub_files if s.startswith(path)]
        module_unbounded = [u for u in unbounded if path.replace("modules/", "") in u or path in u]

        routes_score = min(100, len(routes) * 15) if routes else 0
        svc_score = min(100, len(services) * 8) if services else 0
        repo_score = min(100, len(repos) * 10) if repos else 0
        mig_score = 100 if _has_migration(meta.get("migration", [])) else 50
        test_score = 100 if tests else 0
        stub_penalty = max(0, 100 - len(module_stub) * 15)
        unbounded_penalty = max(0, 100 - len(module_unbounded) * 10)

        completion = round(
            routes_score * 0.20
            + svc_score * 0.25
            + repo_score * 0.20
            + mig_score * 0.15
            + test_score * 0.10
            + stub_penalty * 0.05
            + unbounded_penalty * 0.05,
            1,
        )
        prod = "yes" if completion >= 85 and not module_stub else ("conditional" if completion >= 70 else "no")
        scores[mid] = {
            "name": meta["name"],
            "path": path,
            "completion_pct": completion,
            "services": len(services),
            "routes": len(routes),
            "repos": len(repos),
            "tests": len(tests),
            "stub_files": sorted(module_stub)[:10],
            "unbounded_repos": module_unbounded[:5],
            "production_ready": prod,
        }
    return scores


def compute_scores(module_scores: dict, quality: dict, stubs: dict) -> dict:
    avg_completion = sum(m["completion_pct"] for m in module_scores.values()) / max(len(module_scores), 1)
    code_quality = 10.0
    code_quality -= min(2.0, len(quality["large_files"]) * 0.15)
    code_quality -= min(1.5, stubs["critical_count"] * 0.3)
    code_quality -= min(1.5, quality["silent_except_count"] * 0.005)
    testability = min(10.0, 5.0 + avg_completion / 20)
    maintainability = 10.0
    handlers = APP / "services" / "event_consumers_handlers.py"
    repos = APP / "services" / "repositories.py"
    handlers_loc = len(handlers.read_text(encoding="utf-8").splitlines()) if handlers.exists() else 999
    repos_loc = len(repos.read_text(encoding="utf-8").splitlines()) if repos.exists() else 999
    shim_ok = handlers_loc <= 200 and repos_loc <= 200
    if handlers.exists() and len(handlers.read_text(encoding="utf-8").splitlines()) > 500:
        maintainability -= 2.0
    if repos.exists() and len(repos.read_text(encoding="utf-8").splitlines()) > 500:
        maintainability -= 1.5
    return {
        "code_quality": round(max(0, code_quality), 1),
        "testability": round(testability, 1),
        "maintainability": round(max(0, maintainability), 1),
        "avg_module_completion_pct": round(avg_completion, 1),
    }


def generate_markdown(data: dict) -> str:
    scores = data["scores"]
    ms = data["module_scores"]
    handlers = APP / "services" / "event_consumers_handlers.py"
    repos = APP / "services" / "repositories.py"
    handlers_loc = len(handlers.read_text(encoding="utf-8").splitlines()) if handlers.exists() else 999
    repos_loc = len(repos.read_text(encoding="utf-8").splitlines()) if repos.exists() else 999
    shim_ok = handlers_loc <= 200 and repos_loc <= 200
    lines = [
        "# Enterprise Code Quality & Implementation Completeness Review",
        "",
        f"**Generated:** {data['generated_at']}",
        f"**Scope:** Implementation quality and completeness (architecture/security excluded)",
        "",
        "## Executive Scores",
        "",
        f"| Metric | Score |",
        f"|--------|-------|",
        f"| Code Quality | **{scores['code_quality']}/10** |",
        f"| Testability | **{scores['testability']}/10** |",
        f"| Maintainability | **{scores['maintainability']}/10** |",
        f"| Avg Module Completion | **{scores['avg_module_completion_pct']}%** |",
        "",
        "## Inventories",
        "",
        f"- Python files: {len(data['inventories']['all_python'])}",
        f"- Services: {len(data['inventories']['services'])}",
        f"- Routes: {len(data['inventories']['routes'])}",
        f"- Repositories: {len(data['inventories']['repositories'])}",
        f"- Tests: {len(data['inventories']['tests'])}",
        f"- Legacy routes: {len(data['inventories']['legacy_routes'])}",
        "",
        "## Critical Stubs",
        "",
        f"Count: **{data['stubs']['critical_count']}**",
        "",
        "## Unbounded fetchall",
        "",
        f"Count: **{len(data['unbounded_fetchall'])}**",
        "",
        "## Module Completion Matrix",
        "",
        "| Module | Name | Completion % | Prod Ready | Tests | Stubs |",
        "|--------|------|--------------|------------|-------|-------|",
    ]
    for mid in sorted(ms.keys(), key=lambda x: int(x[1:])):
        m = ms[mid]
        lines.append(
            f"| {mid} | {m['name']} | {m['completion_pct']}% | {m['production_ready']} | {m['tests']} | {len(m['stub_files'])} |"
        )
    lines.extend(
        [
            "",
            "## Production Readiness Checklist",
            "",
            f"- [{'x' if data['stubs']['critical_count'] == 0 else ' '}] critical_stubs_count: 0 (current: {data['stubs']['critical_count']})",
            f"- [{'x' if len(data['unbounded_fetchall']) == 0 else ' '}] unbounded_fetchall_count: 0 (current: {len(data['unbounded_fetchall'])})",
            f"- [{'x' if handlers_loc <= 200 else ' '}] event_consumers_handlers.py under 200 LOC (current: {handlers_loc})",
            f"- [{'x' if shim_ok else ' '}] repositories.py deprecated shim only (current: {repos_loc} LOC)",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fail-on-critical-stubs", action="store_true")
    parser.add_argument("--fail-on-unbounded", action="store_true")
    args = parser.parse_args()

    inventories = scan_inventories()
    stubs = scan_stubs()
    quality = scan_code_quality()
    unbounded = scan_unbounded_fetchall()
    module_scores = score_modules(stubs, unbounded)
    scores = compute_scores(module_scores, quality, stubs)

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inventories": inventories,
        "stubs": stubs,
        "code_quality": quality,
        "unbounded_fetchall": unbounded,
        "module_scores": module_scores,
        "scores": scores,
    }
    OUT_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")
    OUT_MD.write_text(generate_markdown(data), encoding="utf-8")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")
    print("scores", scores)
    print("critical_stubs", stubs["critical_count"])
    print("unbounded_fetchall", len(unbounded))
    if args.fail_on_critical_stubs and stubs["critical_count"] > 0:
        return 1
    if args.fail_on_unbounded and unbounded:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
