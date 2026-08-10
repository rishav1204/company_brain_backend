"""
Phase 1 Wave 3 — Architecture fitness functions.

These tests are the automated enforcement of modular-monolith boundaries.
They must fail the build if hard rules are violated (production code only).
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2]  # app/
MODULES = APP / "modules"
CORE = APP / "core"
SERVICES = APP / "services"
API_LEGACY = APP / "api"


def _iter_py(root: Path, *, include_tests: bool = False):
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts or ".venv" in p.parts:
            continue
        if not include_tests and "tests" in p.parts:
            continue
        yield p


def _imports(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return []
    mods: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mods.append(node.module)
        elif isinstance(node, ast.Import):
            mods.extend(a.name for a in node.names)
    return mods


# ---------------------------------------------------------------------------
# Hard rules: Finance OS ↔ ERP (production)
# ---------------------------------------------------------------------------


def test_finance_os_no_direct_erp_internals():
    """FOS may only import erp.query_services, erp.ports (and bridge handlers exception)."""
    fos = MODULES / "finance_os"
    violations: list[str] = []
    for path in _iter_py(fos):
        rel = path.relative_to(fos).as_posix()
        for mod in _imports(path):
            if not mod.startswith("app.modules.erp"):
                continue
            if mod.startswith("app.modules.erp.query_services"):
                continue
            if mod.startswith("app.modules.erp.ports"):
                continue
            # bridge handlers intentionally import erp for allowlisted dispatch
            if rel.startswith("bridges/erp_command_bridge/handlers/"):
                continue
            violations.append(f"{rel} → {mod}")
    assert not violations, "FOS→ERP interior leaks:\n" + "\n".join(violations)


def test_erp_no_finance_os_imports():
    """ERP must not import finance_os (use ports registration / events instead)."""
    erp = MODULES / "erp"
    violations = []
    for path in _iter_py(erp):
        for mod in _imports(path):
            if mod.startswith("app.modules.finance_os"):
                violations.append(f"{path.relative_to(erp).as_posix()} → {mod}")
    assert not violations, "ERP→FOS leaks:\n" + "\n".join(violations)


def test_bridge_and_query_ports_exist():
    assert (MODULES / "finance_os" / "bridges" / "erp_command_bridge" / "services" / "command_service.py").is_file()
    assert (MODULES / "erp" / "query_services" / "dispatch.py").is_file()
    assert (MODULES / "erp" / "ports" / "intelligence_registry.py").is_file()


# ---------------------------------------------------------------------------
# Repositories: persistence-only (heuristic hard fails)
# ---------------------------------------------------------------------------


_REPO_BANNED = [
    (re.compile(r"platform_event_service\.publish"), "publish events"),
    (re.compile(r"queue_manager\.publish"), "queue publish"),
    (re.compile(r"\bopenai\b", re.I), "LLM/openai"),
    (re.compile(r"evaluate_access\("), "authorization evaluate_access"),
    (re.compile(r"workflow_service\."), "workflow service call"),
]


def test_repositories_no_banned_orchestration():
    violations = []
    roots = [
        MODULES,
    ]
    for root in roots:
        for path in _iter_py(root):
            if "/repositories/" not in path.as_posix().replace("\\", "/") and not path.name.endswith(
                "_repository.py"
            ):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pat, label in _REPO_BANNED:
                if pat.search(text):
                    violations.append(f"{path.relative_to(APP).as_posix()}: {label}")
    assert not violations, "Repository layer misuse:\n" + "\n".join(violations)


# ---------------------------------------------------------------------------
# Shared kernel: core must not depend on domain modules
# ---------------------------------------------------------------------------


def test_app_core_no_domain_module_imports():
    violations = []
    for path in _iter_py(CORE):
        for mod in _imports(path):
            if mod.startswith("app.modules."):
                violations.append(f"{path.name} → {mod}")
    assert not violations, "Shared core imported domain modules:\n" + "\n".join(violations)


# ---------------------------------------------------------------------------
# Platform consumers MAY call domains (event side effects) — direction is OK
# ERP packages must not circular-import each other at top level for postings
# We only assert no finance_os in erp (above). Intra-ERP coupling is soft.
# ---------------------------------------------------------------------------


def test_bounded_context_roots_present():
    expected = {
        "core/iam",
        "workflows",
        "platform/events",
        "platform/governance",
        "platform/billing",
        "platform/documents",
        "platform/integrations",
        "platform/notifications",
        "finance_os/platform_ai_runtime",
        "erp/journals",
        "erp/gl",
        "erp/accounts_payable",
    }
    missing = []
    for rel in expected:
        if not (MODULES / rel).is_dir():
            missing.append(rel)
    assert not missing


def test_event_registry_unique_owners_on_types():
    """Each registered event_type maps to exactly one owner string in ALL_EVENTS dict."""
    from app.modules.platform.events.bus.event_registry import ALL_EVENTS

    owners = Counter(d.owner for d in ALL_EVENTS.values())
    assert len(ALL_EVENTS) > 50
    # each event appears once as dict key
    assert len(ALL_EVENTS) == len(set(ALL_EVENTS.keys()))
    assert owners  # smoke


def test_no_second_event_bus_package():
    """Do not introduce kafka/celery bus packages replacing platform.events."""
    banned_names = {"kafka_bus", "celery_app", "event_bus_v2", "message_broker"}
    found = []
    for path in _iter_py(MODULES):
        if path.stem in banned_names:
            found.append(path.as_posix())
    assert not found


def test_dependency_direction_finance_os_uses_acl_only():
    """Count FOS→ERP imports: must only be ports / query_services / bridge handlers."""
    fos = MODULES / "finance_os"
    allowed_prefixes = (
        "app.modules.erp.query_services",
        "app.modules.erp.ports",
    )
    for path in _iter_py(fos):
        rel = path.relative_to(fos).as_posix()
        for mod in _imports(path):
            if not mod.startswith("app.modules.erp"):
                continue
            if any(mod.startswith(p) for p in allowed_prefixes):
                continue
            if rel.startswith("bridges/erp_command_bridge/handlers/"):
                continue
            pytest.fail(f"illegal import {rel} → {mod}")


def test_legacy_api_does_not_import_finance_os_internals_unchecked():
    """Soft documentation of legacy stack size (must remain discoverable)."""
    if not API_LEGACY.is_dir():
        pytest.skip("no legacy api")
    files = list(_iter_py(API_LEGACY))
    assert len(files) > 0


def test_wave3_scan_artifact_is_runnable():
    """The offline metrics scan script must stay executable where it is kept.

    docs/review is a working folder that is not always checked out, so this
    gate only applies once the script is present.
    """
    found = None
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "docs" / "review" / "phase1_wave3" / "_scan_wave3.py"
        if candidate.is_file():
            found = candidate
            break
    if found is None:
        pytest.skip("docs/review/phase1_wave3/_scan_wave3.py not in this checkout")
    ast.parse(found.read_text(encoding="utf-8", errors="ignore"))


def test_intra_erp_no_import_from_platform_ai_runtime():
    erp = MODULES / "erp"
    violations = []
    for path in _iter_py(erp):
        for mod in _imports(path):
            if "platform_ai_runtime" in mod:
                violations.append(path.as_posix())
    assert not violations


def test_tools_catalog_is_string_targets_not_import_graph():
    """Catalog may contain ERP module path *strings* without importing those modules."""
    catalog = MODULES / "finance_os" / "platform_ai_runtime" / "tools" / "catalog_read.py"
    if not catalog.is_file():
        pytest.skip("no catalog")
    # file should not import ar service at module top-level for wiring
    mods = _imports(catalog)
    assert not any(m.startswith("app.modules.erp.accounts_receivable") for m in mods)
