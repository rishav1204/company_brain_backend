from app.services import event_consumers


def test_agent_plan_not_executed_when_run_not_approved(monkeypatch) -> None:
    executed = {"count": 0}

    def _fake_get_run(org_id: str, run_id: str):
        return {"run_id": run_id, "status": "pending_human_approval"}

    def _fake_execute_action(**kwargs):
        executed["count"] += 1
        return {"status": "completed"}

    monkeypatch.setattr(event_consumers.agents_repo, "get_run", _fake_get_run)
    monkeypatch.setattr(event_consumers, "execute_action", _fake_execute_action)

    event_consumers._consume_agent_plan_event(
        {
            "org_id": "org-demo",
            "payload": {
                "run_id": "run-123",
                "actions": [{"tool": "slack", "method": "postMessage", "params": {"text": "x"}}],
            },
        }
    )

    assert executed["count"] == 0
