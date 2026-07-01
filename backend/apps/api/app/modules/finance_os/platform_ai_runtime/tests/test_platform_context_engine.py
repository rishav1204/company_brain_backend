from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.modules.finance_os.platform_ai_runtime.context.entity_resolver import entity_resolver
from app.modules.finance_os.platform_ai_runtime.context.intent_engine import intent_engine
from app.modules.finance_os.platform_ai_runtime.context.context_planner import context_planner
from app.modules.finance_os.platform_ai_runtime.context.context_compressor import context_compressor
from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import (
    ConversationState,
    IntentResult,
    PlatformContext,
    ResolvedEntity,
)
from app.modules.finance_os.platform_ai_runtime.engine.goal_planner import goal_planner
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import WorldState, WorldStateScreen


def test_intent_gst_read_question() -> None:
    result = intent_engine.classify("How much GST did we pay last quarter?", use_llm=False)
    assert result.intent in {"read", "analysis"}
    assert "gst" in result.suggested_modules or result.intent == "analysis"


def test_intent_create_po_action() -> None:
    result = intent_engine.classify("Create a purchase order for 10 laptops", use_llm=False)
    assert result.intent == "action"


def test_intent_mixed_then_action() -> None:
    result = intent_engine.classify("Show overdue invoices then pay them", use_llm=False)
    assert result.intent == "mixed"


def test_entity_resolver_screen_context() -> None:
    ws = WorldState(screen=WorldStateScreen(module="M11_AP", entity_type="invoice", entity_id="inv-123"))
    entities = entity_resolver.resolve("Why is this pending?", world_state=ws)
    assert any(e.entity_type == "invoice" and e.entity_id == "inv-123" for e in entities)


def test_entity_resolver_period_keyword() -> None:
    entities = entity_resolver.resolve("How much GST last quarter?", world_state=WorldState())
    assert any(e.entity_type == "period" for e in entities)


def test_context_planner_gst_sources() -> None:
    intent = IntentResult(intent="read", confidence=0.9, suggested_modules=["gst"])
    entities = [ResolvedEntity(entity_type="gst", source="nlp_keyword")]
    plan = context_planner.plan(intent=intent, entities=entities, world_state=WorldState(), message="GST paid?")
    source_types = {s.source_type for s in plan.sources}
    assert "erp" in source_types or "bridge" in source_types
    assert "memory" in source_types


def test_context_compressor_token_budget() -> None:
    ctx = PlatformContext(
        intent=IntentResult(intent="read"),
        world_state=WorldState(),
        memory=[{"content": "x" * 500, "title": "GST note"} for _ in range(10)],
        erp_facts={"gst": {"total": 1000, "items": [{"id": i} for i in range(20)]}},
        summaries={},
    )
    compressed = context_compressor.compress(ctx, token_budget=500)
    assert compressed.token_estimate <= 500
    assert compressed.summaries


def test_goal_planner_skips_retrieval_with_platform_context() -> None:
    pctx = PlatformContext(
        intent=IntentResult(intent="action"),
        world_state=WorldState(),
        summaries={"memory": "preloaded context"},
    )
    graph, meta = goal_planner.plan(
        "Do something custom",
        use_llm=False,
        platform_context=pctx,
        skip_retrieval_steps=True,
    )
    tools = {(n.tool, n.method) for n in graph.nodes.values()}
    assert ("memory", "search") not in tools
    assert "pre-loaded" in meta.reasoning.lower() or graph.nodes == {}


@patch("app.modules.finance_os.platform_ai_runtime.context.retrieval_orchestrator.retrieval_orchestrator.fetch")
@patch("app.modules.finance_os.platform_ai_runtime.context.working_memory.working_memory.load")
def test_platform_context_engine_build(mock_wm_load, mock_fetch) -> None:
    from app.modules.finance_os.platform_ai_runtime.context.platform_context_engine import platform_context_engine

    mock_wm_load.return_value = ConversationState()
    mock_fetch.return_value = {
        "memory": [{"content": "Vendor X bills monthly", "final_score": 0.9}],
        "graph": [],
        "erp_facts": {"ap": {"total_outstanding": 42}},
        "documents": [],
        "policies": [],
        "retrieval_trace": [{"source": "memory", "ok": True}],
    }
    ctx = platform_context_engine.build(
        "11111111-1111-4111-8111-111111111111",
        message="Which vendors are paid late?",
        world_state=WorldState(screen=WorldStateScreen(module="M11_AP")),
        user_id="user-1",
    )
    assert ctx.summaries
    assert ctx.intent.intent in {"read", "analysis"}


@patch("app.modules.finance_os.platform_ai_runtime.services.runtime_service.answer_synthesizer")
@patch("app.modules.finance_os.platform_ai_runtime.services.runtime_service.platform_context_engine")
@patch("app.modules.finance_os.platform_ai_runtime.services.runtime_service.goal_repository")
def test_runtime_answer_read_path(mock_repo, mock_pce, mock_synth) -> None:
    from app.modules.finance_os.platform_ai_runtime.services.runtime_service import RuntimeService

    mock_pce.build.return_value = PlatformContext(
        intent=IntentResult(intent="read"),
        world_state=WorldState(),
        summaries={"ap": "Total outstanding: 42L"},
    )
    mock_synth.synthesize.return_value = {
        "answer": "Top delayed vendor is ABC Traders.",
        "sources": {},
        "confidence_band": "review",
    }
    mock_repo.create_goal.return_value = {"id": "goal-1"}
    mock_repo.create_run.return_value = {"id": "run-1"}

    svc = RuntimeService()
    with patch("app.modules.finance_os.platform_ai_runtime.services.runtime_service.settings") as mock_settings:
        mock_settings.m38_context_engine_enabled = True
        mock_settings.m38_read_answer_mode = True
        resp = svc._chat_inner(
            "11111111-1111-4111-8111-111111111111",
            message="Which vendors are paid late?",
            user_id="u1",
            roles=["ap.read"],
            attrs={},
            world_state=WorldState(),
            goal_id=None,
            human_approved=False,
            selected_alternative_index=None,
        )
    assert resp.mode == "answer"
    assert "ABC" in resp.assistant_message
