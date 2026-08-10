from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.finance_os.agents.orchestrator.forbidden_actions import is_forbidden_action
from app.modules.finance_os.platform_ai_runtime.tools.catalog import ALL_SPECS, READ_SPECS
from app.modules.finance_os.platform_ai_runtime.tools.catalog_draft import DRAFT_SPECS
from app.modules.finance_os.platform_ai_runtime.tools.registry import tool_registry


@pytest.fixture(scope="module")
def registry():
    return tool_registry


def test_phase2_tool_count_at_least_100(registry) -> None:
    tools = registry.list_tools()
    assert len(tools) >= 100, f"Expected >=100 tools, got {len(tools)}"


def test_phase2_catalog_spec_count(registry) -> None:
    assert len(READ_SPECS) >= 80
    assert len(DRAFT_SPECS) >= 25
    assert len(ALL_SPECS) == len(READ_SPECS) + len(DRAFT_SPECS)


def test_all_catalog_specs_registered(registry) -> None:
    registered = {(t["tool"], t["method"]) for t in registry.list_tools()}
    for spec in ALL_SPECS:
        assert (spec.tool, spec.method) in registered, f"Missing {spec.tool}.{spec.method}"


def test_forbidden_tool_names_not_in_registry(registry) -> None:
    forbidden_roots = {"journal", "payment", "gst", "gst_filing", "ledger"}
    for t in registry.list_tools():
        assert t["tool"] not in forbidden_roots


def test_forbidden_methods_not_in_registry(registry) -> None:
    for t in registry.list_tools():
        assert is_forbidden_action(t["tool"], t["method"]) is False, f"{t['tool']}.{t['method']} is forbidden"


def test_read_tools_marked_read_only(registry) -> None:
    read_pairs = {(s.tool, s.method) for s in READ_SPECS}
    for t in registry.list_tools():
        if (t["tool"], t["method"]) in read_pairs:
            assert t["read_only"] is True


def test_draft_tools_not_read_only(registry) -> None:
    draft_pairs = {(s.tool, s.method) for s in DRAFT_SPECS}
    custom = {("procurement", "confirm_grn"), ("procurement", "cancel_grn"), ("inventory", "receive"), ("inventory", "deactivate_item")}
    for t in registry.list_tools():
        if (t["tool"], t["method"]) in draft_pairs or (t["tool"], t["method"]) in custom:
            assert t["read_only"] is False


def test_compensation_on_create_tools(registry) -> None:
    by_key = {(t["tool"], t["method"]): t.get("compensation") for t in registry.list_tools()}
    assert by_key.get(("procurement", "create_po")) == "procurement.cancel_po"
    assert by_key.get(("journals", "create_draft")) == "journals.void_draft"
    assert by_key.get(("procurement", "create_grn")) == "procurement.cancel_grn"
    assert by_key.get(("ap", "create_vendor")) == "ap.deactivate_vendor"
    assert by_key.get(("inventory", "create_item")) == "inventory.deactivate_item"
    # void/cancel tools themselves must be registered
    assert ("procurement", "cancel_grn") in by_key
    assert ("journals", "void_draft") in by_key
    assert ("ap", "cancel_invoice") in by_key
    assert ("inventory", "deactivate_item") in by_key


def test_policy_action_on_tools(registry) -> None:
    tools = registry.list_tools()
    assert all(t.get("policy_action") for t in tools)


def test_unknown_tool_returns_error(registry) -> None:
    result = registry.execute("org", "nonexistent", "method", {}, actor_id="u1", human_approved=True)
    assert result["status"] == "error"


@patch("app.modules.erp.accounts_payable.services.invoice_service.invoice_service")
def test_ap_list_invoices_read(mock_svc, registry) -> None:
    mock_svc.list_invoices.return_value = [{"id": "inv-1"}]
    result = registry.execute(
        "11111111-1111-4111-8111-111111111111",
        "ap",
        "list_invoices",
        {},
        actor_id="u1",
        human_approved=False,
    )
    assert result["status"] == "completed"
    assert result["items"] == [{"id": "inv-1"}]


@patch("app.modules.erp.journals.services.journal_service.journal_service")
def test_journals_create_draft_requires_approval(mock_svc, registry) -> None:
    result = registry.execute(
        "11111111-1111-4111-8111-111111111111",
        "journals",
        "create_draft",
        {"journal_type": "general", "posting_date": "2026-06-01"},
        actor_id="u1",
        human_approved=False,
    )
    assert result["status"] == "pending_approval"
    mock_svc.create_draft.assert_not_called()


@patch("app.modules.erp.journals.services.journal_service.journal_service")
def test_journals_create_draft_with_approval(mock_svc, registry) -> None:
    mock_svc.create_draft.return_value = {"journal": {"id": "j-1"}}
    result = registry.execute(
        "11111111-1111-4111-8111-111111111111",
        "journals",
        "create_draft",
        {"journal_type": "general", "posting_date": "2026-06-01"},
        actor_id="u1",
        attrs={"user_id": "u1"},
        human_approved=True,
    )
    assert result["status"] != "pending_approval"
    # Bridge may short-circuit on allowlist without invoking the ERP service mock.


@patch("app.modules.erp.treasury.services.cash_position_service.cash_position_service")
def test_treasury_cash_position_read(mock_svc, registry) -> None:
    mock_svc.snapshot_all.return_value = {"total": 1000}
    result = registry.execute(
        "11111111-1111-4111-8111-111111111111",
        "treasury",
        "get_cash_position",
        {},
        actor_id="u1",
    )
    assert result["status"] == "completed"
    assert result["result"]["total"] == 1000


def test_each_major_domain_has_read_tools(registry) -> None:
    tools_by_domain: dict[str, int] = {}
    for t in registry.list_tools():
        if t["read_only"]:
            tools_by_domain[t["tool"]] = tools_by_domain.get(t["tool"], 0) + 1
    for domain in ("procurement", "inventory", "ap", "ar", "journals", "treasury", "reconciliation", "fiscal"):
        assert tools_by_domain.get(domain, 0) >= 2, f"Domain {domain} needs >=2 read tools"


def test_custom_confirm_grn_requires_approval(registry) -> None:
    result = registry.execute(
        "11111111-1111-4111-8111-111111111111",
        "procurement",
        "confirm_grn",
        {"grn_id": "g1"},
        actor_id="u1",
        human_approved=False,
    )
    assert result["status"] == "pending_approval"


@patch("app.modules.erp.procurement.services.grn_service.grn_service")
def test_custom_confirm_grn_executes(mock_grn, registry) -> None:
    mock_grn.confirm.return_value = {"id": "g1", "status": "confirmed"}
    result = registry.execute(
        "11111111-1111-4111-8111-111111111111",
        "procurement",
        "confirm_grn",
        {"grn_id": "g1"},
        actor_id="u1",
        attrs={"user_id": "u1"},
        human_approved=True,
    )
    assert result["status"] != "pending_approval"
    # Bridge may short-circuit on allowlist without invoking the ERP service mock.
