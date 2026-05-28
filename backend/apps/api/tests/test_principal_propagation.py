from app.services import event_consumers
from app.services.event_bus import event_bus
from app.services.principal_context import build_principal, principal_from_envelope, principal_from_request_context
from app.core.request_context import RequestContext


def test_event_bus_publish_sets_envelope_principal(monkeypatch) -> None:
    monkeypatch.setattr("app.services.event_bus.audit_repo.create_log", lambda **kwargs: None)
    monkeypatch.setattr("app.services.event_bus.event_queue.publish", lambda envelope: None)
    principal = build_principal(user_id="user-a", roles=["controller"], attrs={"dept": "finance"})
    event = event_bus.publish(
        event_type="agent.run.started",
        org_id="org-demo",
        source="test",
        trace_id="trace-1",
        payload={"run_id": "run-1"},
        principal=principal,
    )
    assert event["principal"]["user_id"] == "user-a"
    assert event["principal"]["roles"] == ["controller"]
    assert event["principal"]["attrs"] == {"dept": "finance"}


def test_principal_from_envelope_prefers_root_over_payload() -> None:
    envelope = {
        "principal": build_principal(user_id="root-user", roles=["cfo"], attrs={}),
        "payload": {
            "principal": build_principal(user_id="payload-user", roles=["viewer"], attrs={}),
        },
    }
    resolved = principal_from_envelope(envelope)
    assert resolved["user_id"] == "root-user"
    assert resolved["roles"] == ["cfo"]


def test_principal_from_envelope_defaults_to_system_worker() -> None:
    resolved = principal_from_envelope({"payload": {}})
    assert resolved["roles"] == ["system_worker"]
    assert resolved["user_id"] == "system-worker"


def test_principal_from_request_context() -> None:
    context = RequestContext(
        request_id="req-1",
        org_id="org-demo",
        user_id="user-42",
        roles=["tenant_admin"],
        source_acl=["source:erp"],
        attrs={"region": "us-east"},
    )
    principal = principal_from_request_context(context, human_approved=True)
    assert principal["user_id"] == "user-42"
    assert principal["roles"] == ["tenant_admin"]
    assert principal["source_acl"] == ["source:erp"]
    assert principal["human_approved"] is True


def test_agent_run_consumer_uses_envelope_principal(monkeypatch) -> None:
    observed = {"roles": None, "attrs": None}

    def _fake_run_langgraph_flow(**kwargs):
        observed["roles"] = kwargs.get("principal_roles")
        observed["attrs"] = kwargs.get("principal_attrs")
        return {"status": "completed", "proposed_actions": []}

    monkeypatch.setattr(event_consumers, "run_langgraph_flow", _fake_run_langgraph_flow)
    monkeypatch.setattr(
        event_consumers.agents_repo,
        "create_run",
        lambda **kwargs: {"run_id": "run-99", "status": kwargs.get("status", "completed")},
    )

    event_consumers._consume_agent_run_event(
        {
            "org_id": "org-demo",
            "trace_id": "trace-99",
            "principal": build_principal(user_id="user-7", roles=["controller"], attrs={"team": "ap"}),
            "payload": {"agent_type": "workflow_assistant", "trigger_type": "event"},
        }
    )
    assert observed["roles"] == ["controller"]
    assert observed["attrs"] == {"team": "ap"}


def test_publish_child_event_forwards_principal(monkeypatch) -> None:
    captured = {}

    def _fake_publish(**kwargs):
        captured.update(kwargs)
        return {"event_id": "evt-1", **kwargs}

    monkeypatch.setattr(event_consumers.event_bus, "publish", _fake_publish)

    event_consumers._publish_child_event(
        {
            "trace_id": "trace-forward",
            "principal": build_principal(user_id="user-forward", roles=["analyst"], attrs={"scope": "read"}),
            "payload": {},
        },
        event_type="source.sync.completed",
        org_id="org-demo",
        source="worker.ingestion",
        payload={"source_id": "src-1"},
    )
    assert captured["principal"]["user_id"] == "user-forward"
    assert captured["principal"]["roles"] == ["analyst"]
    assert captured["trace_id"] == "trace-forward"


def test_agent_action_consumer_uses_actor_id_from_principal(monkeypatch) -> None:
    observed = {"actor_id": None, "roles": None}

    def _fake_execute_action(**kwargs):
        observed["actor_id"] = kwargs.get("actor_id")
        observed["roles"] = kwargs.get("roles")
        return {"status": "completed"}

    monkeypatch.setattr(event_consumers, "execute_action", _fake_execute_action)

    event_consumers._consume_agent_action_event(
        {
            "org_id": "org-demo",
            "principal": build_principal(user_id="user-action", roles=["controller"], attrs={}),
            "payload": {"tool": "slack", "method": "postMessage", "params": {"text": "hello"}},
        }
    )
    assert observed["actor_id"] == "user-action"
    assert observed["roles"] == ["controller"]
