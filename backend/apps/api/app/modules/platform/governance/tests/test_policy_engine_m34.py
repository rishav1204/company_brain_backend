from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.platform.governance.engine import approval_engine, policy_cache_engine, risk_engine, rule_engine, sod_engine
from app.modules.platform.governance.engine.policy_engine import PolicyEvaluationResult, evaluate
from app.modules.platform.governance.policies import ALL_SEED_POLICIES
from app.modules.platform.governance.services.policy_service import governance_policy_service


ORG = "00000000-0000-0000-0000-000000000001"


# --- sod engine ---


def test_sod_blocks_same_actor_invoice_approve() -> None:
    msg = sod_engine.check_sod(action="invoice.approve", created_by="u1", actor_user_id="u1", org_id=ORG)
    assert msg is not None


def test_sod_allows_different_actor() -> None:
    msg = sod_engine.check_sod(action="invoice.approve", created_by="u1", actor_user_id="u2", org_id=ORG)
    assert msg is None


def test_sod_skips_non_maker_checker_action() -> None:
    msg = sod_engine.check_sod(action="read", created_by="u1", actor_user_id="u1", org_id=ORG)
    assert msg is None


def test_agent_denies_journal_post() -> None:
    msg = sod_engine.check_agent_restrictions(actor_type="agent", action="journal.post")
    assert msg is not None
    assert "Agent cannot perform" in msg


def test_agent_denies_payment_execute() -> None:
    msg = sod_engine.check_agent_restrictions(actor_type="agent", action="payment.execute")
    assert msg is not None


def test_agent_denies_gst_file() -> None:
    msg = sod_engine.check_agent_restrictions(actor_type="agent", action="gst.file")
    assert msg is not None


def test_agent_allows_recommend() -> None:
    msg = sod_engine.check_agent_restrictions(actor_type="agent", action="agent.recommend")
    assert msg is None


def test_human_actor_not_restricted() -> None:
    msg = sod_engine.check_agent_restrictions(actor_type="user", action="journal.post")
    assert msg is None


def test_ai_actor_type_restricted() -> None:
    msg = sod_engine.check_agent_restrictions(actor_type="ai", action="post_journal")
    assert msg is not None


# --- risk engine ---


def test_risk_low_small_amount() -> None:
    assert risk_engine.assess_risk(action="payment.execute", attrs={"amount": 1000}) == "LOW"


def test_risk_medium_half_million() -> None:
    assert risk_engine.assess_risk(action="payment.execute", attrs={"amount": 600_000}) == "MEDIUM"


def test_risk_high_two_point_five_million() -> None:
    assert risk_engine.assess_risk(action="payment.execute", attrs={"amount": 3_000_000}) == "HIGH"


def test_risk_critical_fiscal_closed() -> None:
    assert risk_engine.assess_risk(action="journal.post", attrs={"fiscal_period_open": False}) == "CRITICAL"


def test_risk_read_action_ignores_fiscal_closed() -> None:
    assert risk_engine.assess_risk(action="approval.read", attrs={"fiscal_period_open": False}) == "LOW"
    assert risk_engine.requires_open_fiscal_period("approval.read") is False
    assert risk_engine.requires_open_fiscal_period("journal.post") is True


def test_evaluate_read_allowed_when_fiscal_closed() -> None:
    result = evaluate(
        ORG,
        action="approval.read",
        attrs={"fiscal_period_open": False},
        roles=["tenant_admin", "cfo"],
        dry_run=True,
    )
    assert result.allowed is True
    assert result.decision == "allowed"


def test_risk_critical_blacklisted_vendor() -> None:
    assert risk_engine.assess_risk(action="payment.execute", attrs={"vendor_risk": "blacklisted"}) == "CRITICAL"


def test_risk_high_vendor_risk() -> None:
    assert risk_engine.assess_risk(action="payment.execute", attrs={"vendor_risk": "high", "amount": 1000}) == "HIGH"


def test_risk_blocks_critical() -> None:
    assert risk_engine.risk_blocks_execution("CRITICAL", human_approved=False) is True


def test_risk_does_not_block_low() -> None:
    assert risk_engine.risk_blocks_execution("LOW", human_approved=False) is False


# --- approval engine legacy tiers ---


@pytest.mark.parametrize(
    "amount,expected_roles",
    [
        (10_000, ["finance_manager"]),
        (75_000, ["finance_manager", "controller"]),
        (600_000, ["finance_manager", "controller", "cfo"]),
        (3_000_000, ["finance_manager", "controller", "cfo", "dual_approval"]),
    ],
)
def test_legacy_payment_policy_tiers(amount: float, expected_roles: list[str]) -> None:
    result = approval_engine.to_legacy_payment_policy(amount, "vendor_payment", [])
    assert result["required_roles"] == expected_roles


def test_legacy_tax_payment_adds_cfo() -> None:
    result = approval_engine.to_legacy_payment_policy(
        150_000, "tax_payment", [{"level": 1, "role": "finance_manager"}]
    )
    assert "cfo" in result["required_roles"]


def test_required_roles_missing_detects_gap() -> None:
    chain = [{"level": 1, "role": "cfo"}, {"level": 2, "role": "controller"}]
    missing = approval_engine.required_roles_missing(chain, ["finance_manager"])
    assert "cfo" in missing
    assert "controller" in missing


def test_elevated_role_bypasses_matrix() -> None:
    chain = [{"level": 1, "role": "cfo"}]
    assert approval_engine.required_roles_missing(chain, ["tenant_admin"]) == []


def test_normalize_action_payment_aliases() -> None:
    assert approval_engine._normalize_action("approve_payment") == "payment.execute"
    assert approval_engine._normalize_action("post_journal") == "journal.post"


@patch("app.modules.platform.governance.engine.approval_engine.approval_matrix_repository")
def test_resolve_chain_from_matrix(mock_repo: MagicMock) -> None:
    mock_repo.schema_ready.return_value = True
    mock_repo.list_active.return_value = [
        {"min_amount": 0, "max_amount": 50000, "approver_role": "finance_manager", "level": 1},
        {"min_amount": 50000, "max_amount": None, "approver_role": "controller", "level": 2},
    ]
    policy_cache_engine.invalidate_org(ORG)
    chain = approval_engine.resolve_chain(ORG, action="payment.execute", amount=75_000)
    assert any(c["role"] == "controller" for c in chain)


# --- rule engine ---


def test_rule_applies_action_filter() -> None:
    rule = {"conditions": {"action": "journal.post"}}
    assert rule_engine.rule_applies(rule, "journal.post", {}) is True
    assert rule_engine.rule_applies(rule, "payment.execute", {}) is False


def test_rule_applies_amount_gt() -> None:
    rule = {"conditions": {"action": "journal.post", "amount_gt": 500000}}
    assert rule_engine.rule_applies(rule, "journal.post", {"amount": 600000}) is True
    assert rule_engine.rule_applies(rule, "journal.post", {"amount": 100000}) is False


def test_evaluate_rule_fiscal_block() -> None:
    rule = {"policy_type": "fiscal", "actions": {"block": True}}
    msg = rule_engine.evaluate_rule(rule, {"fiscal_period_open": False}, [])
    assert msg == "Fiscal period is closed"


def test_evaluate_rule_require_role() -> None:
    rule = {"policy_type": "approval", "actions": {"block": True, "require_role": "controller"}}
    msg = rule_engine.evaluate_rule(rule, {}, ["finance_manager"])
    assert "controller" in (msg or "")


@patch("app.modules.platform.governance.engine.rule_engine.load_rules")
def test_evaluate_rules_returns_violation(mock_load: MagicMock) -> None:
    mock_load.return_value = [
        {
            "policy_key": "FISCAL_PERIOD_LOCK",
            "policy_type": "fiscal",
            "conditions": {"closed_period": True},
            "actions": {"block": True},
        }
    ]
    violations = rule_engine.evaluate_rules(ORG, action="journal.post", attrs={"fiscal_period_open": False}, roles=[])
    assert len(violations) == 1


# --- cache engine ---


def test_cache_set_and_get() -> None:
    policy_cache_engine.invalidate_org(ORG)
    policy_cache_engine.set_cached(ORG, "rules", [{"id": "r1"}])
    assert policy_cache_engine.get_cached(ORG, "rules") == [{"id": "r1"}]


def test_cache_invalidate_clears() -> None:
    policy_cache_engine.set_cached(ORG, "rules", [{"id": "r1"}])
    policy_cache_engine.invalidate_org(ORG)
    assert policy_cache_engine.get_cached(ORG, "rules") is None


def test_cache_key_format() -> None:
    assert policy_cache_engine._cache_key(ORG, "matrix") == f"policy:matrix:{ORG}"


# --- policy engine facade ---


def test_evaluate_allows_basic_payment_dry_run() -> None:
    result = evaluate(
        ORG,
        action="payment.execute",
        attrs={"amount": 1000},
        roles=["finance_manager", "tenant_admin"],
        actor_user_id="u1",
        dry_run=True,
    )
    assert result.allowed is True
    assert result.decision == "allowed"


def test_evaluate_denies_agent_journal_post() -> None:
    result = evaluate(
        ORG,
        action="journal.post",
        attrs={"amount": 1000},
        roles=["finance_manager"],
        actor_type="agent",
        dry_run=True,
    )
    assert result.allowed is False
    assert result.decision == "denied"


@patch("app.modules.platform.governance.engine.policy_engine.approval_engine.resolve_chain")
def test_evaluate_approval_required_high_amount(mock_resolve: MagicMock) -> None:
    mock_resolve.return_value = [
        {"level": 1, "role": "finance_manager"},
        {"level": 2, "role": "controller"},
        {"level": 3, "role": "cfo"},
    ]
    result = evaluate(
        ORG,
        action="payment.execute",
        attrs={"amount": 600_000},
        roles=["finance_manager"],
        dry_run=True,
    )
    assert result.allowed is False
    assert result.decision == "approval_required"


def test_evaluate_allows_with_elevated_role() -> None:
    result = evaluate(
        ORG,
        action="payment.execute",
        attrs={"amount": 600_000},
        roles=["tenant_admin"],
        dry_run=True,
    )
    assert result.allowed is True


def test_evaluate_sod_violation_dry_run() -> None:
    result = evaluate(
        ORG,
        action="invoice.approve",
        attrs={},
        roles=["approver"],
        created_by="same-user",
        actor_user_id="same-user",
        dry_run=True,
    )
    assert result.allowed is False
    assert any(v.get("type") == "maker_checker" for v in result.violations)


def test_evaluate_override_required_fiscal_closed() -> None:
    result = evaluate(
        ORG,
        action="journal.post",
        attrs={"amount": 1000, "fiscal_period_open": False},
        roles=["finance_manager"],
        dry_run=True,
    )
    assert result.allowed is False
    assert result.decision == "override_required"


@patch("app.modules.platform.governance.engine.rule_engine.load_rules")
def test_evaluate_rule_denial(mock_load: MagicMock) -> None:
    mock_load.return_value = [
        {
            "policy_key": "TEST_BLOCK",
            "policy_type": "fiscal",
            "conditions": {"closed_period": True},
            "actions": {"block": True},
        }
    ]
    result = evaluate(
        ORG,
        action="journal.post",
        attrs={"fiscal_period_open": False},
        roles=["controller"],
        dry_run=True,
    )
    assert result.allowed is False
    assert result.decision == "denied"


def test_policy_evaluation_result_legacy_dict() -> None:
    result = PolicyEvaluationResult(
        allowed=True,
        approval_chain=[{"level": 1, "role": "cfo"}],
    )
    legacy = result.to_legacy_payment_policy_dict(amount=100_000, payment_type="vendor_payment")
    assert legacy["required_roles"] == ["cfo"]


# --- governance service delegation ---


def test_governance_service_evaluate_dry_run() -> None:
    result = governance_policy_service.evaluate(
        ORG,
        action="payment.execute",
        attrs={"amount": 1000},
        roles=["tenant_admin"],
        dry_run=True,
    )
    assert result.allowed is True


def test_governance_service_maker_checker_via_service() -> None:
    result = governance_policy_service.evaluate(
        ORG,
        action="invoice.approve",
        attrs={},
        roles=["approver"],
        created_by="u1",
        actor_user_id="u1",
        dry_run=True,
    )
    assert result.allowed is False


# --- seed catalogs ---


def test_all_seed_policies_non_empty() -> None:
    assert len(ALL_SEED_POLICIES) >= 5


def test_seed_policies_have_codes() -> None:
    codes = [p["policy_code"] for p in ALL_SEED_POLICIES]
    assert len(codes) == len(set(codes))


def test_banking_seed_policy_present() -> None:
    assert any(p["policy_code"] == "PAYMENT_THRESHOLD_001" for p in ALL_SEED_POLICIES)


def test_agent_seed_policy_present() -> None:
    assert any(p["policy_code"] == "AGENT_EXECUTION_DENY" for p in ALL_SEED_POLICIES)


def test_journal_seed_policy_present() -> None:
    assert any(p["policy_code"] == "JOURNAL_MANUAL_001" for p in ALL_SEED_POLICIES)


def test_gst_seed_policy_present() -> None:
    assert any(p["policy_code"] == "GST_FILING_RECON_001" for p in ALL_SEED_POLICIES)


def test_close_seed_policy_present() -> None:
    assert any(p["policy_code"] == "FISCAL_PERIOD_LOCK" for p in ALL_SEED_POLICIES)


# --- ERP delegation ---


def test_payment_policy_engine_delegates_with_org() -> None:
    from app.modules.erp.banking.engine.payment_policy_engine import evaluate_payment_policy

    result = evaluate_payment_policy(org_id=ORG, amount=600_000, payment_type="vendor_payment", roles=["finance_manager"])
    assert result["requires_cfo"] is True
    assert "cfo" in result["required_roles"]


def test_payment_policy_engine_no_org_fallback() -> None:
    from app.modules.erp.banking.engine.payment_policy_engine import evaluate_payment_policy

    result = evaluate_payment_policy(amount=600_000, payment_type="vendor_payment", roles=["finance_manager"])
    assert "cfo" in result["required_roles"]


def test_treasury_transfer_roles_delegates() -> None:
    from app.modules.erp.treasury.engine.transfer_engine import approval_roles_for_amount

    roles = approval_roles_for_amount(100_000)
    assert "finance_manager" in roles


def test_pr_workflow_uses_matrix_when_org() -> None:
    from app.modules.erp.procurement.workflows.pr_approval_workflow import resolve_approval_chain

    chain = resolve_approval_chain(600_000, org_id=ORG)
    assert isinstance(chain, list)
    assert len(chain) >= 1


def test_pr_workflow_legacy_fallback() -> None:
    from app.modules.erp.procurement.workflows.pr_approval_workflow import resolve_approval_chain

    chain = resolve_approval_chain(600_000)
    assert "cfo" in chain or "controller" in chain


def test_policy_reasoner_with_org_id() -> None:
    from app.modules.finance_os.agents.ai.policy_reasoner import check

    flags = check({"action": "journal.post", "amount": 1000}, org_id=ORG, roles=["finance_manager"])
    assert isinstance(flags, list)


def test_policy_reasoner_legacy_fallback() -> None:
    from app.modules.finance_os.agents.ai.policy_reasoner import check

    flags = check({"amount": 600000})
    assert "high_amount" in flags


# --- workflow matrix feed ---


def test_build_approval_chain_uses_matrix_metadata() -> None:
    from app.modules.workflows.engine.approval_chain import build_approval_chain

    with patch("app.modules.platform.governance.engine.approval_engine.resolve_chain") as mock_resolve:
        mock_resolve.return_value = [{"level": 1, "role": "cfo"}]
        chain = build_approval_chain({}, {"org_id": ORG, "amount": 600_000, "action_code": "vendor_payment"})
        assert chain == [{"level": 1, "role": "cfo"}]


def test_build_approval_chain_explicit_overrides() -> None:
    from app.modules.workflows.engine.approval_chain import build_approval_chain

    chain = build_approval_chain({"approval_chain": [{"level": 1, "role": "custom"}]}, {"amount": 1000})
    assert chain == [{"level": 1, "role": "custom"}]


# --- events / M33 ---


def test_policy_events_registered() -> None:
    from app.modules.platform.events.bus.event_registry import ALL_EVENTS

    for evt in (
        "policy.approved",
        "policy.denied",
        "policy.override.required",
        "policy.risk.detected",
        "policy.evaluated",
    ):
        assert evt in ALL_EVENTS


def test_m33_materializes_policy_events() -> None:
    from app.modules.finance_os.audit_explorer.pipelines.audit_materialization_pipeline import MATERIALIZE_EVENT_TYPES

    for evt in ("policy.evaluated", "policy.denied", "policy.override.required"):
        assert evt in MATERIALIZE_EVENT_TYPES


def test_event_consumer_wires_policy_events() -> None:
    from pathlib import Path

    text = Path(__file__).resolve().parents[4].joinpath("services", "event_consumers.py").read_text(encoding="utf-8")
    assert "_consume_policy_events" in text
    assert "policy.evaluated" in text
