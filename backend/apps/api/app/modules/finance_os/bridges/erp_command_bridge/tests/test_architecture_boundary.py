"""Architecture boundary + registry/lifecycle tests for Phase 1 Wave 1 ERP ACL."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[5]  # app/
MODULES = APP_ROOT / "modules"
FOS = MODULES / "finance_os"
ERP = MODULES / "erp"
BRIDGE = FOS / "bridges" / "erp_command_bridge"


def _iter_py(root: Path):
    for p in root.rglob("*.py"):
        if any(part in {"tests", "__pycache__", ".venv"} for part in p.parts):
            continue
        yield p


def _imports_of(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    mods: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mods.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                mods.append(alias.name)
    return mods


def test_finance_os_no_direct_erp_service_or_repo_imports():
    violations = []
    for path in _iter_py(FOS):
        rel = path.relative_to(FOS).as_posix()
        if rel.startswith("bridges/erp_command_bridge/handlers/"):
            for mod in _imports_of(path):
                if mod.startswith("app.modules.erp.") and not mod.startswith("app.modules.erp.query_services"):
                    violations.append(f"{rel} imports {mod}")
            continue
        if rel.startswith("bridges/"):
            for mod in _imports_of(path):
                if mod.startswith("app.modules.erp.") and not any(
                    mod.startswith(p)
                    for p in (
                        "app.modules.erp.query_services",
                        "app.modules.erp.ports",
                    )
                ):
                    violations.append(f"{rel} imports {mod}")
            continue
        for mod in _imports_of(path):
            if not mod.startswith("app.modules.erp"):
                continue
            if mod.startswith("app.modules.erp.query_services"):
                continue
            violations.append(f"{rel} imports {mod}")
    assert not violations, "Forbidden Finance OS → ERP imports:\n" + "\n".join(violations)


def test_erp_no_finance_os_imports():
    violations = []
    for path in _iter_py(ERP):
        rel = path.relative_to(ERP).as_posix()
        for mod in _imports_of(path):
            if mod.startswith("app.modules.finance_os"):
                violations.append(f"{rel} imports {mod}")
    assert not violations, "Forbidden ERP → Finance OS imports:\n" + "\n".join(violations)


def test_bridge_package_exists():
    assert (BRIDGE / "services" / "command_service.py").is_file()
    assert (BRIDGE / "registry" / "command_registry.py").is_file()
    assert (BRIDGE / "contracts" / "lifecycle.py").is_file()
    assert (BRIDGE / "contracts" / "contexts.py").is_file()
    assert (BRIDGE / "contracts" / "errors.py").is_file()
    assert (ERP / "query_services" / "dispatch.py").is_file()
    assert (ERP / "query_services" / "registry.py").is_file()
    assert (ERP / "ports" / "intelligence_registry.py").is_file()


def test_command_service_exports():
    from app.modules.finance_os.bridges.erp_command_bridge.services.command_service import erp_command_service
    from app.modules.finance_os.bridges.erp_command_bridge.contracts.command_envelope import ErpCommand
    from app.modules.finance_os.bridges.erp_command_bridge.contracts.contexts import (
        AuthorizationContext,
        ApprovalContext,
        CommandContext,
        ExecutionContext,
    )

    assert erp_command_service is not None
    cmd = ErpCommand(command_type="Test", org_id="org", actor_id="u1")
    assert cmd.version == "v1"
    assert cmd.command_id
    ctx = CommandContext(
        command=cmd,
        authorization=AuthorizationContext(user_id="u1"),
        approval=ApprovalContext(),
        execution=ExecutionContext(),
    )
    assert ctx.correlation_id


def test_bootstrap_registers_ports_and_registries():
    from app.modules.erp.ports.intelligence_registry import intelligence_registry
    from app.modules.erp.query_services.registry import query_registry
    from app.modules.finance_os.bridges.erp_command_bridge.bootstrap import bootstrap_wave1_boundaries
    from app.modules.finance_os.bridges.erp_command_bridge.registry.command_registry import command_registry

    bootstrap_wave1_boundaries()
    assert intelligence_registry.try_invoice() is not None
    assert intelligence_registry.try_forecast() is not None
    assert intelligence_registry.invoice_version() == "v1"
    assert command_registry.get_optional("CreateVoucherFromExtraction") is not None
    assert command_registry.get_by_tool("vouchers", "create_from_extraction") is not None
    assert len(command_registry.list_commands()) >= 1
    assert query_registry.get("GetCashPosition") is not None
    assert query_registry.get("ListOutstandingAp") is not None
    names = {q["name"] for q in query_registry.list_queries()}
    assert "GetVendorByGstin" in names


def test_mutation_not_allowlisted_raises():
    from app.modules.finance_os.bridges.erp_command_bridge.exceptions import CommandTargetNotAllowlisted
    from app.modules.finance_os.bridges.erp_command_bridge.handlers.erp_dispatch import dispatch_erp_call
    from app.modules.finance_os.bridges.erp_command_bridge.bootstrap import bootstrap_wave1_boundaries

    bootstrap_wave1_boundaries()
    with pytest.raises(CommandTargetNotAllowlisted):
        dispatch_erp_call(
            "org",
            module="app.modules.erp.gl.services.posting_service",
            service="posting_service",
            fn="post",
            kwargs={},
        )


def test_tool_spec_blocks_direct_erp_resolve():
    from app.modules.finance_os.platform_ai_runtime.tools.tool_spec import ToolSpec, _resolve_callable

    spec = ToolSpec(
        tool="ap",
        method="create_invoice",
        module="app.modules.erp.accounts_payable.services.invoice_service",
        service="invoice_service",
        fn="create_invoice",
        read_only=False,
    )
    with pytest.raises(ValueError, match="erp_direct_forbidden"):
        _resolve_callable(spec)


def test_unregistered_command_fails_validation():
    from app.modules.finance_os.bridges.erp_command_bridge.bootstrap import bootstrap_wave1_boundaries
    from app.modules.finance_os.bridges.erp_command_bridge.contracts.command_envelope import ErpCommand
    from app.modules.finance_os.bridges.erp_command_bridge.services.command_service import erp_command_service

    bootstrap_wave1_boundaries()
    result = erp_command_service.execute(
        ErpCommand(
            command_type="DefinitelyNotRegisteredCommand",
            org_id="00000000-0000-0000-0000-000000000001",
            actor_id="tester",
            payload={},
            human_approved=True,
        ),
        skip_approval_gate=True,
        skip_authz_on_human_approved=True,
    )
    assert result.status == "failed"
    assert result.error_code in {"COMMAND_NOT_REGISTERED", "VALIDATION_FAILED", "ERP_NOT_ALLOWLISTED", "UNKNOWN"} or (
        result.detail and "not_registered" in (result.detail or "").lower()
    )


def test_query_not_registered():
    from app.modules.erp.query_services.registry import QueryNotRegisteredError, query_registry
    from app.modules.finance_os.bridges.erp_command_bridge.bootstrap import bootstrap_wave1_boundaries

    bootstrap_wave1_boundaries()
    with pytest.raises(QueryNotRegisteredError):
        query_registry.execute("NoSuchQuery", "org-x")


def test_lifecycle_transitions_documented():
    from app.modules.finance_os.bridges.erp_command_bridge.contracts.lifecycle import (
        CommandLifecycle,
        can_transition,
    )

    assert can_transition(CommandLifecycle.REQUESTED, CommandLifecycle.VALIDATED)
    assert can_transition(CommandLifecycle.AUTHORIZED, CommandLifecycle.EXECUTING)
    assert not can_transition(CommandLifecycle.EXECUTED, CommandLifecycle.REQUESTED)


def test_error_taxonomy_classify():
    from app.modules.finance_os.bridges.erp_command_bridge.exceptions import (
        CommandAuthorizationError,
        CommandValidationError,
        classify_exception,
    )
    from app.modules.finance_os.bridges.erp_command_bridge.contracts.errors import ErrorClass

    c, code, retry = classify_exception(CommandAuthorizationError("x"))
    assert c == ErrorClass.AUTHORIZATION
    assert retry is False
    c2, _, retry2 = classify_exception(CommandValidationError("y"))
    assert c2 == ErrorClass.VALIDATION
    assert retry2 is False


def test_bridge_core_no_repository_imports():
    """Performance rule: bridge core modules must not import ERP repositories."""
    violations = []
    for path in _iter_py(BRIDGE):
        rel = path.relative_to(BRIDGE).as_posix()
        if rel.startswith("adapters/") or rel.startswith("tests/"):
            continue
        for mod in _imports_of(path):
            if ".repositories." in mod and mod.startswith("app.modules.erp"):
                violations.append(f"{rel} -> {mod}")
    assert not violations, "Bridge core imported ERP repositories:\n" + "\n".join(violations)


def test_command_registry_rejects_repository_target():
    from app.modules.finance_os.bridges.erp_command_bridge.registry.command_registry import (
        CommandRegistration,
        command_registry,
    )

    with pytest.raises(ValueError, match="repositories"):
        command_registry.register(
            CommandRegistration(
                name="BadRepoCommand",
                erp_module="app.modules.erp.accounts_payable.repositories.invoice_repository",
                erp_service="invoice_repository",
                erp_fn="list",
            )
        )


def test_request_hash_stable():
    from app.modules.finance_os.bridges.erp_command_bridge.contracts.command_envelope import ErpCommand
    from app.modules.finance_os.bridges.erp_command_bridge.idempotency.strategy import request_hash

    a = ErpCommand(command_type="X", org_id="o", actor_id="u", payload={"a": 1})
    b = ErpCommand(command_type="X", org_id="o", actor_id="u", payload={"a": 1})
    assert request_hash(a.stable_hash_material()) == request_hash(b.stable_hash_material())
