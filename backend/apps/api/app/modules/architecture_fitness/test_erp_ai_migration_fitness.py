"""
Architecture fitness functions for the ERP → Finance OS AI migration.

Intelligence lives in Finance OS. ERP reaches it through the typed ports in
``erp/ports/intelligence_registry.py`` only, so no ``erp/<domain>/ai/`` package
may come back and no module may import the helpers that were moved.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[2]  # app/
MODULES = APP / "modules"
ERP = MODULES / "erp"
FOS = MODULES / "finance_os"

MIGRATED_DOMAINS = (
    "ap",
    "ar",
    "assets",
    "banking",
    "compliance",
    "expenses",
    "inventory",
    "journals",
    "payments",
    "procurement",
    "reconciliation",
    "tax",
    "treasury",
)


def _iter_py(root: Path):
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts or ".venv" in path.parts:
            continue
        yield path


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
            mods.extend(alias.name for alias in node.names)
    return mods


def test_no_erp_ai_packages():
    """No ERP bounded context may host its own ``ai`` package."""
    offenders = sorted(
        p.relative_to(MODULES).as_posix()
        for p in ERP.rglob("ai")
        if p.is_dir() and "__pycache__" not in p.parts
    )
    assert not offenders, (
        "ERP AI packages must live in finance_os/domain_intelligence:\n" + "\n".join(offenders)
    )


def test_nothing_imports_moved_erp_ai_helpers():
    """Every call site (tests included) must use the port or the FOS module."""
    violations: list[str] = []
    for path in _iter_py(APP):
        for mod in _imports(path):
            parts = mod.split(".")
            if parts[:3] == ["app", "modules", "erp"] and "ai" in parts[3:]:
                violations.append(f"{path.relative_to(APP).as_posix()} → {mod}")
    assert not violations, "imports of removed ERP AI modules:\n" + "\n".join(violations)


def test_domain_intelligence_packages_exist():
    missing = [
        domain
        for domain in MIGRATED_DOMAINS
        if not (FOS / "domain_intelligence" / domain / "__init__.py").is_file()
    ]
    assert not missing, f"finance_os/domain_intelligence packages missing: {missing}"


def test_every_port_has_an_adapter_registration():
    """Each declared port name is registered by the ERP command bridge bootstrap."""
    from app.modules.erp.ports.intelligence_registry import PORT_NAMES

    bootstrap = FOS / "bridges" / "erp_command_bridge" / "bootstrap.py"
    text = bootstrap.read_text(encoding="utf-8")
    missing = [
        name
        for name in PORT_NAMES
        if f'"{name}"' not in text and f"register_{name}(" not in text
    ]
    assert not missing, f"ports never registered in bootstrap: {missing}"


def test_erp_ai_call_sites_go_through_the_registry():
    """ERP services/routes that still expose AI endpoints must reference the registry."""
    ai_facades = [
        ERP / "accounts_payable" / "services" / "ai_invoice_service.py",
        ERP / "accounts_receivable" / "services" / "ai_collection_service.py",
        ERP / "expenses" / "services" / "ai_expense_service.py",
        ERP / "journals" / "services" / "ai_journal_service.py",
    ]
    violations = [
        p.relative_to(MODULES).as_posix()
        for p in ai_facades
        if p.is_file() and "intelligence_registry" not in p.read_text(encoding="utf-8")
    ]
    assert not violations, "ERP AI facades bypassing the port:\n" + "\n".join(violations)
