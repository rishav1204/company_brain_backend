from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.platform.events.bus.event_registry import get_event_definition


def test_migration_059_exists() -> None:
    mig = Path(__file__).resolve().parents[7] / "migrations" / "059_policy_engine.sql"
    assert mig.exists()
    text = mig.read_text(encoding="utf-8")
    assert "governance.policies" in text
    assert "governance.policy_decisions" in text
    assert "governance.approval_matrix" in text
    assert "governance.policy_exceptions" in text


def test_bootstrap_governance_policies_script_exists() -> None:
    script = Path(__file__).resolve().parents[7] / "scripts" / "bootstrap_governance_policies.py"
    assert script.exists()
    assert "ALL_SEED_POLICIES" in script.read_text(encoding="utf-8")


def test_policy_engine_routes_module() -> None:
    path = Path(__file__).resolve().parents[1] / "routes" / "policy_engine_routes.py"
    text = path.read_text(encoding="utf-8")
    assert "/policies/evaluate" in text
    assert "/policies/decisions" in text
    assert "/policies/approval-matrix" in text
    assert "/policies/sod" in text
    assert "/policies/exceptions" in text


def test_governance_router_includes_policy_engine() -> None:
    text = Path(__file__).resolve().parents[1].joinpath("routes", "router.py").read_text(encoding="utf-8")
    assert "policy_engine_routes" in text


def test_domain_policy_modules_exist() -> None:
    base = Path(__file__).resolve().parents[1] / "policies"
    for name in (
        "banking_policies.py",
        "treasury_policies.py",
        "journal_policies.py",
        "ap_policies.py",
        "gst_policies.py",
        "close_policies.py",
        "agent_policies.py",
    ):
        assert (base / name).exists(), name


def test_engine_modules_exist() -> None:
    base = Path(__file__).resolve().parents[1] / "engine"
    for name in (
        "policy_engine.py",
        "rule_engine.py",
        "risk_engine.py",
        "approval_engine.py",
        "sod_engine.py",
        "policy_cache_engine.py",
    ):
        assert (base / name).exists(), name


def test_repository_modules_exist() -> None:
    base = Path(__file__).resolve().parents[1] / "repositories"
    assert (base / "policy_decision_repository.py").exists()
    assert (base / "approval_matrix_repository.py").exists()
    assert (base / "policy_exception_repository.py").exists()


def test_policy_events_module() -> None:
    path = Path(__file__).resolve().parents[1] / "events" / "policy_events.py"
    text = path.read_text(encoding="utf-8")
    assert "emit_policy_approved" in text
    assert "emit_policy_denied" in text


def test_event_definition_policy_approved() -> None:
    defn = get_event_definition("policy.approved")
    assert defn is not None
    assert defn.event_type == "policy.approved"


def test_event_definition_policy_evaluated() -> None:
    defn = get_event_definition("policy.evaluated")
    assert defn is not None


def test_access_control_calls_policy_engine() -> None:
    text = Path(__file__).resolve().parents[3].joinpath(
        "core", "iam", "services", "access_control.py"
    ).read_text(encoding="utf-8")
    assert "policy_engine_evaluate" in text


def test_root_policy_service_no_hardcoded_50000() -> None:
    text = Path(__file__).resolve().parents[4].joinpath("services", "policy_service.py").read_text(encoding="utf-8")
    assert "amount > 50000" not in text
    assert "amount_threshold_delegated_to_policy_engine" in text


def test_approval_gate_no_hardcoded_50000() -> None:
    text = Path(__file__).resolve().parents[3].joinpath(
        "core", "iam", "services", "approval_gate_service.py"
    ).read_text(encoding="utf-8")
    assert "50000" not in text


def test_payment_policy_engine_no_hardcoded_tiers() -> None:
    text = Path(__file__).resolve().parents[3].joinpath(
        "erp", "banking", "engine", "payment_policy_engine.py"
    ).read_text(encoding="utf-8")
    assert "50_000" not in text or "policy_engine" in text


def test_reconciliation_route_policy_gate() -> None:
    text = Path(__file__).resolve().parents[3].joinpath(
        "erp", "reconciliation", "routes", "reconciliation_routes.py"
    ).read_text(encoding="utf-8")
    assert "reconciliation.override" in text


def test_agent_context_passes_org_id() -> None:
    text = Path(__file__).resolve().parents[3].joinpath(
        "finance_os", "agents", "services", "context_service.py"
    ).read_text(encoding="utf-8")
    assert "org_id=org_id" in text


@patch("app.modules.platform.governance.routes.policy_engine_routes.evaluate")
def test_evaluate_route_handler(mock_eval: MagicMock) -> None:
    from app.modules.platform.governance.routes.policy_engine_routes import evaluate_policy, PolicyEvaluateRequest

    mock_eval.return_value = MagicMock(
        allowed=True,
        decision="allowed",
        reason="ok",
        violations=[],
        risk_level="LOW",
        approval_chain=[],
        decision_id="d1",
    )
    ctx = MagicMock(org_id="org-1", user_id="u1", roles=["admin"], request_id="req-1")
    out = evaluate_policy(PolicyEvaluateRequest(action="payment.execute", attrs={"amount": 100}), ctx)
    assert out["allowed"] is True
    mock_eval.assert_called_once()


@patch("app.modules.platform.governance.routes.policy_engine_routes.policy_decision_repository")
def test_list_decisions_route(mock_repo: MagicMock) -> None:
    from app.modules.platform.governance.routes.policy_engine_routes import list_decisions

    mock_repo.list_decisions.return_value = [{"id": "1"}]
    ctx = MagicMock(org_id="org-1", request_id="req-1")
    out = list_decisions(ctx)
    assert out["count"] == 1


@patch("app.modules.platform.governance.routes.policy_engine_routes.approval_matrix_repository")
def test_list_matrix_route(mock_repo: MagicMock) -> None:
    from app.modules.platform.governance.routes.policy_engine_routes import list_approval_matrix

    mock_repo.list_active.return_value = [{"approver_role": "cfo"}]
    ctx = MagicMock(org_id="org-1", request_id="req-1")
    out = list_approval_matrix(ctx)
    assert len(out["items"]) == 1


def test_sod_catalog_route() -> None:
    from app.modules.platform.governance.routes.policy_engine_routes import sod_catalog

    ctx = MagicMock(request_id="req-1")
    out = sod_catalog(ctx)
    assert "maker_checker_actions" in out
    assert isinstance(out["maker_checker_actions"], list)


@patch("app.modules.platform.governance.routes.policy_engine_routes.policy_exception_repository")
def test_create_exception_route(mock_repo: MagicMock) -> None:
    from app.modules.platform.governance.routes.policy_engine_routes import create_exception, ExceptionRequest

    mock_repo.create.return_value = {"id": "ex-1", "status": "pending"}
    ctx = MagicMock(org_id="org-1", request_id="req-1")
    out = create_exception(
        ExceptionRequest(policy_code="TEST", action="journal.post", reason="test exception"),
        ctx,
    )
    assert out["exception"]["id"] == "ex-1"


def test_m34_doc_exists() -> None:
    doc = Path(__file__).resolve().parents[7] / "ERP_MODULES" / "M34_policy_engine.md"
    assert doc.exists()
    assert "Golden rule" in doc.read_text(encoding="utf-8")


def test_erp_master_map_references_m34() -> None:
    text = Path(__file__).resolve().parents[7].joinpath("ERP_MASTER_MODULE_MAP.md").read_text(encoding="utf-8")
    assert "M34" in text
    assert "Policy Engine" in text
