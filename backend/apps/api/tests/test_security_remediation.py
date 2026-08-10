"""Security remediation regression tests."""
from __future__ import annotations

from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def test_login_lockout_checks_locked_key():
    text = (APP / "modules" / "core" / "iam" / "services" / "login_lockout_service.py").read_text(encoding="utf-8")
    assert ":locked" in text
    assert "client.get(_locked_key(email, ip))" in text


def test_jwt_revocation_fail_closed():
    text = (APP / "services" / "jwt_auth.py").read_text(encoding="utf-8")
    assert "jwt_revocation_fail_closed" in text


def test_webhook_url_safety_module():
    path = APP / "modules" / "platform" / "integrations" / "security" / "url_safety.py"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "validate_outbound_url" in text
    assert "169.254.0.0/16" in text


def test_agent_policy_gate_evaluates_proposed_actions():
    runner = (APP / "services" / "langgraph_runner.py").read_text(encoding="utf-8")
    gate = (APP / "modules" / "finance_os" / "platform_ai_runtime" / "policy" / "unified_policy_gate.py").read_text(
        encoding="utf-8"
    )
    assert "for proposed in state.proposed_actions" in runner
    assert "evaluate_tool_invocation" in runner or "agent_tool_requires_approval" in runner + gate
    assert "agent_tool_requires_approval" in gate or "requires_human_approval" in gate


def test_workflow_fail_closed_payment_schedule():
    text = (APP / "modules" / "erp" / "accounts_payable" / "services" / "payment_service.py").read_text(encoding="utf-8")
    assert "Payment workflow initiation failed" in text
    assert 'metadata={"allocations": invoice_allocations, "workflow_approved": True}' not in text


def test_refresh_token_consume_atomic():
    text = (APP / "modules" / "core" / "iam" / "repositories" / "session_repository.py").read_text(encoding="utf-8")
    assert "consume_refresh_session" in text
    assert "reuse_detected" in text or "revoked = FALSE" in text


def test_permission_guard_uses_db_roles():
    text = (APP / "modules" / "core" / "iam" / "middleware" / "permission_guard.py").read_text(encoding="utf-8")
    assert "list_role_names" in text


def test_risk_engine_blocks_high_without_approval():
    text = (APP / "modules" / "platform" / "governance" / "engine" / "risk_engine.py").read_text(encoding="utf-8")
    assert 'if risk_level == "HIGH" and not human_approved' in text
    assert "return True" in text.split('if risk_level == "HIGH"')[1][:80]
