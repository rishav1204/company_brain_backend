from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.finance_os.audit_explorer.engine.timeline_engine import (
    parse_object_ref,
    resolve_object_from_envelope,
    build_timeline,
)
from app.modules.finance_os.audit_explorer.engine.trace_engine import trace_related_events
from app.modules.finance_os.audit_explorer.engine.evidence_engine import collect_evidence
from app.modules.finance_os.audit_explorer.engine.lineage_engine import get_entity_lineage
from app.modules.finance_os.audit_explorer.validators.ai_context_validator import validate_ai_context, sanitize_metadata
from app.modules.finance_os.audit_explorer.security.audit_explorer_guard import (
    require_audit_read,
    require_audit_copilot,
    require_audit_refresh,
)
from app.modules.finance_os.audit_explorer.ai.evidence_analyzer import analyze_evidence
from app.modules.finance_os.audit_explorer.pipelines.audit_materialization_pipeline import (
    MATERIALIZE_EVENT_TYPES,
    materialize_from_envelope,
)
from app.modules.platform.events.bus.event_registry import ALL_EVENTS, get_event_definition


# --- object ref ---


def test_parse_object_ref_erp_invoice() -> None:
    et, eid, ref = parse_object_ref("erp:invoice:abc-123")
    assert et == "invoice"
    assert eid == "abc-123"
    assert "erp:invoice:abc-123" in (ref or "")


def test_parse_object_ref_invalid() -> None:
    et, eid, ref = parse_object_ref(None)
    assert et is None
    assert eid is None


def test_parse_object_ref_no_colons() -> None:
    et, eid, ref = parse_object_ref("plain")
    assert et is None
    assert ref == "plain"


def test_resolve_object_from_envelope_invoice() -> None:
    env = {
        "event_type": "invoice.created",
        "entity_type": "invoice",
        "entity_id": "inv-1",
        "payload": {},
    }
    ot, oid, ref = resolve_object_from_envelope(env)
    assert ot == "invoice"
    assert oid == "inv-1"
    assert ref is not None


def test_resolve_object_from_envelope_workflow() -> None:
    env = {
        "event_type": "workflow.approved",
        "payload": {"workflow_instance_id": "wf-99"},
    }
    ot, oid, _ = resolve_object_from_envelope(env)
    assert ot == "workflow"
    assert oid == "wf-99"


def test_resolve_object_from_envelope_agent() -> None:
    env = {
        "event_type": "agent.completed",
        "payload": {"execution_id": "exec-1"},
    }
    ot, oid, _ = resolve_object_from_envelope(env)
    assert ot == "agent_execution"
    assert oid == "exec-1"


def test_resolve_object_from_payload_object_ref() -> None:
    env = {
        "event_type": "journal.posted",
        "payload": {"object_ref": "erp:journal:j-1"},
    }
    ot, oid, _ = resolve_object_from_envelope(env)
    assert ot == "journal"
    assert oid == "j-1"


# --- AI context validator ---


def test_validate_ai_context_clean() -> None:
    assert validate_ai_context({"factor": "vendor_history"}) == {"factor": "vendor_history"}


def test_validate_ai_context_rejects_prompt() -> None:
    with pytest.raises(ValueError, match="Forbidden"):
        validate_ai_context({"prompt": "secret"})


def test_validate_ai_context_rejects_cot() -> None:
    with pytest.raises(ValueError, match="Forbidden"):
        validate_ai_context({"chain_of_thought": "hidden"})


def test_validate_ai_context_rejects_raw_llm() -> None:
    with pytest.raises(ValueError, match="Forbidden"):
        validate_ai_context({"raw_llm_output": "x"})


def test_sanitize_metadata_strips_forbidden() -> None:
    result = sanitize_metadata({"prompt": "x", "ok": 1})
    assert "prompt" not in result
    assert result.get("ok") == 1


def test_sanitize_metadata_empty() -> None:
    assert sanitize_metadata(None) == {}


def test_validate_ai_context_nested_forbidden() -> None:
    with pytest.raises(ValueError):
        validate_ai_context({"meta": {"full_prompt": "bad"}})


# --- security guards ---


def test_require_audit_read_auditor() -> None:
    require_audit_read(MagicMock(roles=["auditor"]))


def test_require_audit_read_compliance() -> None:
    require_audit_read(MagicMock(roles=["compliance_officer"]))


def test_require_audit_read_cfo() -> None:
    require_audit_read(MagicMock(roles=["cfo"]))


def test_require_audit_read_denied() -> None:
    with pytest.raises(HTTPException) as exc:
        require_audit_read(MagicMock(roles=["viewer"]))
    assert exc.value.status_code == 403


def test_require_audit_copilot_allowed() -> None:
    require_audit_copilot(MagicMock(roles=["finance_manager"]))


def test_require_audit_copilot_denied() -> None:
    with pytest.raises(HTTPException):
        require_audit_copilot(MagicMock(roles=["viewer"]))


def test_require_audit_refresh_admin() -> None:
    require_audit_refresh(MagicMock(roles=["tenant_admin"]))


def test_require_audit_refresh_denied_auditor() -> None:
    with pytest.raises(HTTPException):
        require_audit_refresh(MagicMock(roles=["auditor"]))


# --- evidence analyzer ---


def test_analyze_evidence_empty() -> None:
    result = analyze_evidence([])
    assert result["count"] == 0


def test_analyze_evidence_by_type() -> None:
    items = [{"evidence_type": "pdf"}, {"evidence_type": "pdf"}, {"evidence_type": "approval"}]
    result = analyze_evidence(items)
    assert result["count"] == 3
    assert result["by_type"]["pdf"] == 2
    assert result["has_approval"] is True


def test_analyze_evidence_policy() -> None:
    result = analyze_evidence([{"evidence_type": "policy"}])
    assert result["has_policy"] is True


# --- materialization ---


def test_materialize_event_types_includes_audit_log() -> None:
    assert "audit.log.created" in MATERIALIZE_EVENT_TYPES


def test_materialize_event_types_includes_journal() -> None:
    assert "journal.posted" in MATERIALIZE_EVENT_TYPES


def test_materialize_event_types_includes_agent() -> None:
    assert "agent.completed" in MATERIALIZE_EVENT_TYPES


def test_materialize_skips_no_org() -> None:
    assert materialize_from_envelope({})["status"] == "skipped"


def test_materialize_skips_unknown_event() -> None:
    result = materialize_from_envelope({"org_id": "o1", "event_type": "unknown.xyz"})
    assert result["status"] == "skipped"


@patch("app.modules.finance_os.audit_explorer.pipelines.audit_materialization_pipeline.emit_timeline_updated")
@patch("app.modules.finance_os.audit_explorer.pipelines.audit_materialization_pipeline.timeline_repository")
def test_materialize_invoice_created(mock_timeline, mock_emit) -> None:
    mock_timeline.upsert.return_value = {"id": "t1", "object_type": "invoice", "object_id": "i1"}
    env = {
        "org_id": "org-1",
        "event_type": "invoice.created",
        "event_id": "e1",
        "entity_type": "invoice",
        "entity_id": "i1",
        "payload": {},
    }
    result = materialize_from_envelope(env)
    assert result["status"] == "ok"
    mock_emit.assert_called_once()


# --- event registry ---


def test_audit_timeline_updated_registered() -> None:
    assert "audit.timeline.updated" in ALL_EVENTS


def test_audit_evidence_linked_registered() -> None:
    assert "audit.evidence.linked" in ALL_EVENTS


def test_audit_ai_decision_recorded_registered() -> None:
    assert "audit.ai_decision.recorded" in ALL_EVENTS


def test_audit_timeline_updated_source() -> None:
    defn = get_event_definition("audit.timeline.updated")
    assert defn is not None
    assert defn.owner == "finance_os.audit_explorer"


# --- engines with mocks ---


@patch("app.modules.finance_os.audit_explorer.engine.timeline_engine.timeline_repository")
@patch("app.modules.finance_os.audit_explorer.engine.timeline_engine.audit_read_models")
def test_build_timeline_materialized(mock_audit, mock_repo) -> None:
    mock_repo.list_for_object.return_value = [
        {"id": "1", "event_type": "invoice.created", "event_timestamp": "2024-01-01"}
    ]
    mock_repo.list_for_timeline = MagicMock(return_value=[])
    with patch(
        "app.modules.finance_os.audit_explorer.engine.timeline_engine.audit_evidence_repository.list_for_timeline",
        return_value=[],
    ):
        items = build_timeline("org", object_type="invoice", object_id="i1")
    assert len(items) >= 1


@patch("app.modules.finance_os.audit_explorer.engine.trace_engine.correlate_by_trace")
def test_trace_related_events(mock_corr) -> None:
    mock_corr.return_value = [{"event_type": "x"}]
    assert len(trace_related_events("org", "trace-1")) == 1


def test_trace_related_events_no_trace() -> None:
    assert trace_related_events("org", None) == []


@patch("app.modules.finance_os.audit_explorer.engine.evidence_engine.audit_evidence_repository")
@patch("app.modules.finance_os.audit_explorer.engine.evidence_engine.audit_read_models")
def test_collect_evidence(mock_audit, mock_repo) -> None:
    mock_repo.list_for_object.return_value = [{"evidence_type": "pdf"}]
    mock_audit.list_governance_evidence.return_value = [{"evidence_type": "invoice"}]
    result = collect_evidence("org", object_type="invoice", object_id="i1")
    assert len(result["materialized"]) == 1
    assert len(result["governance"]) == 1


@patch("app.modules.finance_os.audit_explorer.engine.lineage_engine.graph_memory_read_models")
def test_get_entity_lineage(mock_gm) -> None:
    mock_gm.get_lineage.return_value = {"count": 2}
    result = get_entity_lineage("org", "e1")
    assert result["count"] == 2


@patch("app.modules.finance_os.audit_explorer.engine.lineage_engine.graph_memory_read_models")
def test_get_entity_lineage_error(mock_gm) -> None:
    mock_gm.get_lineage.side_effect = RuntimeError("neo4j down")
    result = get_entity_lineage("org", "e1")
    assert result["count"] == 0


# --- AI reasoning engine ---


@patch("app.modules.finance_os.audit_explorer.engine.ai_reasoning_engine.ai_decision_repository")
@patch("app.modules.finance_os.audit_explorer.engine.ai_reasoning_engine.agent_read_models")
@patch("app.modules.finance_os.audit_explorer.engine.ai_reasoning_engine.graph_memory_read_models")
def test_explain_execution_with_trails(mock_mem, mock_agent, mock_repo) -> None:
    from app.modules.finance_os.audit_explorer.engine.ai_reasoning_engine import explain_execution

    mock_repo.get_by_execution.return_value = [{"reasoning_summary": "ledger suggested", "ai_trace_id": None}]
    mock_agent.get_execution.return_value = {"entity_type": "invoice", "entity_id": "i1"}
    mock_agent.list_recommendations.return_value = []
    mock_mem.search_entity_memories.return_value = []
    result = explain_execution("org", "exec-1")
    assert len(result["trails"]) == 1


@patch("app.modules.finance_os.audit_explorer.engine.ai_reasoning_engine.ai_decision_repository")
@patch("app.modules.finance_os.audit_explorer.engine.ai_reasoning_engine.agent_read_models")
@patch("app.modules.finance_os.audit_explorer.engine.ai_reasoning_engine.graph_memory_read_models")
def test_explain_execution_fallback_recommendations(mock_mem, mock_agent, mock_repo) -> None:
    from app.modules.finance_os.audit_explorer.engine.ai_reasoning_engine import explain_execution

    mock_repo.get_by_execution.return_value = []
    mock_agent.get_execution.return_value = None
    mock_agent.list_recommendations.return_value = [
        {"recommendation_type": "ledger", "recommendation": "Cloud Hosting", "confidence_score": 0.97, "status": "proposed", "id": "r1"}
    ]
    mock_mem.search_entity_memories.return_value = []
    result = explain_execution("org", "exec-1")
    assert len(result["trails"]) == 1
    assert result["trails"][0]["confidence_score"] == 0.97


# --- audit copilot ---


def test_audit_copilot_no_llm() -> None:
    from unittest.mock import MagicMock, patch
    import app.modules.finance_os.audit_explorer.ai.audit_copilot as copilot_mod

    mock_llm = MagicMock()
    mock_llm.is_ready.return_value = False
    with patch.object(copilot_mod, "llm_provider", mock_llm), patch.object(
        copilot_mod, "generate_explanation", return_value={"context": "timeline info", "sources": {}}
    ):
        result = copilot_mod.answer("org", "Who approved this?")
    assert "timeline info" in result["answer"]


def test_audit_copilot_with_llm() -> None:
    from unittest.mock import MagicMock, patch
    import app.modules.finance_os.audit_explorer.ai.audit_copilot as copilot_mod

    mock_llm = MagicMock()
    mock_llm.is_ready.return_value = True
    mock_llm.generate_json.return_value = {"answer": "Manager approved", "confidence_band": "strong"}
    with patch.object(copilot_mod, "llm_provider", mock_llm), patch.object(
        copilot_mod, "generate_explanation", return_value={"context": "ctx", "sources": {"timeline": []}}
    ):
        result = copilot_mod.answer("org", "Who approved?", object_type="invoice", object_id="i1")
    assert result["answer"] == "Manager approved"


# --- repository validator integration ---


def test_ai_decision_repository_rejects_prompt_in_context() -> None:
    from app.modules.finance_os.audit_explorer.repositories.ai_decision_repository import ai_decision_repository

    with patch.object(ai_decision_repository, "schema_ready", return_value=False):
        result = ai_decision_repository.upsert(
            "org",
            decision_type="test",
            reasoning_summary="ok",
            input_context={"prompt": "secret"},
        )
        assert result.get("id") == "skipped"

    with patch.object(ai_decision_repository, "schema_ready", return_value=True):
        with pytest.raises(ValueError):
            ai_decision_repository.upsert(
                "org",
                decision_type="test",
                reasoning_summary="ok",
                input_context={"prompt": "secret"},
            )


# --- workflow trace service ---


def test_get_approval_chain() -> None:
    from unittest.mock import patch

    from app.modules.finance_os.audit_explorer.services.workflow_trace_service import get_approval_chain

    with patch(
        "app.modules.finance_os.audit_explorer.read_models.workflow_read_models.get_workflow_instance",
        return_value={"workflow_type": "AP_INVOICE"},
    ), patch(
        "app.modules.finance_os.audit_explorer.read_models.workflow_read_models.list_approvals",
        return_value=[{"decision": "approved", "level": 1}],
    ), patch(
        "app.modules.finance_os.audit_explorer.read_models.workflow_read_models.list_workflow_steps",
        return_value=[{"step_type": "approval"}],
    ):
        result = get_approval_chain("org", "wf-1")
    assert len(result["approvals"]) == 1
    assert len(result["steps"]) == 1


# --- search service ---


@patch("app.modules.finance_os.audit_explorer.services.audit_search_service.timeline_repository")
def test_search_materialized(mock_repo) -> None:
    from app.modules.finance_os.audit_explorer.services.audit_search_service import search

    mock_repo.search.return_value = [{"event_type": "invoice.created"}]
    items = search("org", q="INV-1001")
    assert len(items) == 1


@patch("app.modules.finance_os.audit_explorer.services.audit_search_service.audit_read_models")
@patch("app.modules.finance_os.audit_explorer.services.audit_search_service.timeline_repository")
def test_search_fallback_governance(mock_repo, mock_audit) -> None:
    from app.modules.finance_os.audit_explorer.services.audit_search_service import search

    mock_repo.search.return_value = []
    mock_audit.list_governance_logs.return_value = [
        {"id": "1", "entity_type": "invoice", "entity_id": "i1", "event_type": "invoice.created", "action": "invoice.created", "actor_id": "u1", "created_at": "2024", "payload_jsonb": {}, "object_ref": "ref"}
    ]
    items = search("org", q="invoice")
    assert len(items) == 1


# --- explorer service ---


@patch("app.modules.finance_os.audit_explorer.services.audit_explorer_service.get_entity_lineage")
@patch("app.modules.finance_os.audit_explorer.services.audit_explorer_service.ai_decision_repository")
@patch("app.modules.finance_os.audit_explorer.services.audit_explorer_service.collect_evidence")
@patch("app.modules.finance_os.audit_explorer.services.audit_explorer_service.build_timeline")
def test_explore_object(mock_tl, mock_ev, mock_ai, mock_lin) -> None:
    from app.modules.finance_os.audit_explorer.services.audit_explorer_service import explore

    mock_tl.return_value = [{"event_type": "created"}]
    mock_ev.return_value = {"materialized": [], "governance": [{"evidence_type": "pdf"}]}
    mock_ai.get_by_execution.return_value = []
    mock_lin.return_value = {"count": 0}
    result = explore("org", object_type="invoice", object_id="i1")
    assert len(result["timeline"]) == 1
    assert len(result["evidence"]) == 1
