from app.services import event_consumers
from app.services import policy_service

_LEGACY = "app.modules.platform.events.consumers.handlers.legacy_handlers"


def test_execution_policy_requires_approval_for_high_risk_without_human_approval() -> None:
    decision = policy_service.evaluate_action_execution_policy(
        roles=["tenant_admin"],
        attrs={},
        action="approve_payment",
        object_type="action",
        amount=90000,
        vendor_risk="high",
        human_approved=False,
    )
    assert decision.allowed is False
    assert decision.reason == "human_approval_required"


def test_agent_plan_consumer_passes_human_approved_true(monkeypatch) -> None:
    observed = {"human_approved": None, "roles": None, "actor_id": None}

    monkeypatch.setattr(
        f"{_LEGACY}.agents_repo.get_run",
        lambda org_id, run_id: {"run_id": run_id, "status": "approved"},
    )

    def _fake_execute_action(**kwargs):
        observed["human_approved"] = kwargs.get("human_approved")
        observed["roles"] = kwargs.get("roles")
        observed["actor_id"] = kwargs.get("actor_id")
        return {"status": "completed"}

    monkeypatch.setattr(f"{_LEGACY}.execute_action", _fake_execute_action)

    event_consumers._consume_agent_plan_event(
        {
            "org_id": "org-demo",
            "principal": {"user_id": "approver-1", "roles": ["controller"], "attrs": {}, "human_approved": True},
            "payload": {
                "run_id": "run-approved",
                "actions": [{"tool": "slack", "method": "postMessage", "params": {"text": "approved"}}],
            },
        }
    )
    assert observed["human_approved"] is True
    assert observed["roles"] == ["controller"]
    assert observed["actor_id"] == "approver-1"
