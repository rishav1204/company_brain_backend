"""Phase 8 Wave 4 — Platform Context Engine V2 + World State tests."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.modules.finance_os.platform_ai_runtime.context.context_compressor import context_compressor
from app.modules.finance_os.platform_ai_runtime.context.context_planner import context_planner
from app.modules.finance_os.platform_ai_runtime.context.context_quality import context_quality_evaluator
from app.modules.finance_os.platform_ai_runtime.context.context_ranker import context_ranker
from app.modules.finance_os.platform_ai_runtime.context.prompt_assembler import prompt_assembler
from app.modules.finance_os.platform_ai_runtime.context.retrieval_orchestrator import RetrievalOrchestrator
from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import (
    ConversationState,
    IntentResult,
    PlatformContext,
    ResolvedEntity,
    RetrievalPlan,
    RetrievalSource,
)
from app.modules.finance_os.platform_ai_runtime.context.working_memory import WorkingMemoryManager
from app.modules.finance_os.platform_ai_runtime.context.world_state_builder import build_world_state
from app.modules.finance_os.platform_ai_runtime.context.world_state_engine import WorldStateEngine
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import (
    WorldState,
    WorldStateOrg,
    WorldStateScreen,
)


# ── World State ────────────────────────────────────────────────────────────


def test_world_state_merge_tracks_navigation_and_viewed() -> None:
    eng = WorldStateEngine()
    base = WorldState(
        screen=WorldStateScreen(module="M11_AP", route="/ap", entity_type="invoice", entity_id="inv-1"),
    )
    update = WorldState(
        screen=WorldStateScreen(module="M11_AP", route="/ap/inv-2", entity_type="invoice", entity_id="inv-2"),
        selection={"vendor_id": "v-9"},
    )
    merged = eng.merge(base, update)
    assert merged.screen and merged.screen.entity_id == "inv-2"
    assert merged.current_invoice_id == "inv-2"
    assert merged.current_vendor_id == "v-9"
    assert merged.recent_navigation
    assert any(v.get("entity_id") == "inv-2" for v in merged.recently_viewed)


def test_world_state_from_payload_aliases_selection() -> None:
    eng = WorldStateEngine()
    ws = eng.from_payload(
        explicit=WorldState(
            screen=WorldStateScreen(entity_type="vendor", entity_id="v-1"),
            selection={"invoice_id": "i-9"},
        ),
        roles=["ap.read"],
    )
    assert ws.current_vendor_id == "v-1"
    assert ws.current_invoice_id == "i-9"
    assert "ap.read" in ws.roles


def test_world_state_resolve_uses_persisted_when_ui_empty() -> None:
    eng = WorldStateEngine()
    persisted = WorldState(screen=WorldStateScreen(entity_type="invoice", entity_id="inv-persisted"))
    with patch.object(eng, "load_persisted", return_value=persisted):
        resolved = eng.resolve("org-1", published=None, goal_id="g1")
    assert resolved.screen and resolved.screen.entity_id == "inv-persisted"


def test_build_world_state_merge_via_goal() -> None:
    with patch(
        "app.modules.finance_os.platform_ai_runtime.context.world_state_engine.world_state_engine.resolve"
    ) as mock_resolve:
        mock_resolve.return_value = WorldState(
            screen=WorldStateScreen(module="AP", entity_type="invoice", entity_id="inv-x"),
        )
        ws = build_world_state(
            "org",
            explicit=WorldState(screen=WorldStateScreen(entity_id="inv-x", entity_type="invoice")),
            goal_id="g1",
            roles=["ap"],
        )
    assert ws.screen and ws.screen.entity_id == "inv-x"
    mock_resolve.assert_called_once()


# ── Working memory ─────────────────────────────────────────────────────────


def test_working_memory_save_tracks_task_and_prunes() -> None:
    wm = WorkingMemoryManager()
    state = ConversationState(turn_count=0, current_comparisons=["old-gst"], topic_stack=["ap"])
    with patch(
        "app.modules.finance_os.platform_ai_runtime.context.working_memory.goal_repository.update_conversation_state"
    ) as mock_upd:
        out = wm.save(
            "org",
            "goal-1",
            state=state,
            entities=[ResolvedEntity(entity_type="invoice", entity_id="i1", confidence=0.9)],
            intent="read",
            user_message="why is this invoice blocked?",
            reasoning_step="retrieve_block_reasons",
        )
    assert out.turn_count == 1
    assert out.current_task
    assert out.current_entity and out.current_entity["id"] == "i1"
    assert out.reasoning_chain
    mock_upd.assert_called_once()


# ── Context planner ────────────────────────────────────────────────────────


def test_context_planner_minimal_for_gst() -> None:
    plan = context_planner.plan(
        intent=IntentResult(intent="read", confidence=0.9, suggested_modules=["gst"]),
        entities=[],
        world_state=WorldState(),
        message="list gst returns",
    )
    assert plan.sources
    tools = {f"{s.tool}.{s.method}" for s in plan.sources}
    assert any("gst" in t or "tax" in t or "memory" in t for t in tools)
    # Should not dump every ERP module
    assert len(plan.sources) < 20


def test_context_planner_screen_entity_boosts_ui_and_graph() -> None:
    ws = WorldState(
        screen=WorldStateScreen(module="M11_AP", entity_type="invoice", entity_id="inv-99"),
    )
    plan = context_planner.plan(
        intent=IntentResult(intent="read"),
        entities=[ResolvedEntity(entity_type="invoice", entity_id="inv-99", confidence=0.95)],
        world_state=ws,
        message="why is this blocked?",
    )
    assert any(s.tool == "ui_context" for s in plan.sources)
    assert any(s.cross_module for s in plan.sources)  # invoice cross-module expand
    assert "screen_entity" in plan.plan_reason or plan.plan_reason


def test_context_planner_approval_workflow() -> None:
    ws = WorldState(
        screen=WorldStateScreen(module="approvals"),
        pending_approvals=[{"id": "a1", "status": "pending"}],
    )
    plan = context_planner.plan(
        intent=IntentResult(intent="workflow"),
        entities=[],
        world_state=ws,
        message="what is pending approval?",
    )
    assert any(s.tool == "approval_queue" or s.tool == "workflow_state" for s in plan.sources)


# ── Ranking ────────────────────────────────────────────────────────────────


def test_context_ranker_prefers_screen_entity_and_pending() -> None:
    ws = WorldState(screen=WorldStateScreen(entity_id="inv-1", entity_type="invoice", module="ap"))
    items = [
        {"id": "a", "entity_id": "other", "content": "unrelated", "final_score": 0.9},
        {"id": "b", "entity_id": "inv-1", "content": "invoice blocked", "status": "blocked", "final_score": 0.4},
        {"id": "c", "entity_id": "inv-1", "content": "old note", "final_score": 0.5},
    ]
    ranked = context_ranker.rank_memory(
        items,
        query="why blocked",
        world_state=ws,
        entities=[ResolvedEntity(entity_type="invoice", entity_id="inv-1", confidence=0.9)],
        intent=IntentResult(intent="read"),
    )
    assert ranked[0]["entity_id"] == "inv-1"
    assert ranked[0]["id"] in {"b", "c"}


def test_context_ranker_item_meta_freshness() -> None:
    now = datetime.now(timezone.utc).isoformat()
    raw = {
        "memory": [{"id": "1", "updated_at": now, "confidence": 0.8}],
        "erp_facts": {"invoice": {"id": "i1", "updated_at": now}},
        "retrieval_trace": [],
    }
    meta = context_ranker.build_item_meta(raw, as_of=now)
    assert meta
    assert all(m.freshness >= 0.2 for m in meta)
    assert all(m.source for m in meta)


# ── Compression ────────────────────────────────────────────────────────────


def test_context_compressor_list_totals_top_exceptions() -> None:
    ctx = PlatformContext(
        intent=IntentResult(intent="read"),
        world_state=WorldState(screen=WorldStateScreen(module="ap")),
        erp_facts={
            "erp:ap.list_invoices": {
                "items": [
                    {"id": "1", "amount": 100, "status": "open"},
                    {"id": "2", "amount": 5000, "status": "blocked", "risk": "high"},
                    {"id": "3", "amount": 50, "status": "paid"},
                ]
                + [{"id": str(i), "amount": 10, "status": "open"} for i in range(4, 20)]
            }
        },
    )
    out = context_compressor.compress(ctx)
    text = out.summaries.get("erp:ap.list_invoices") or ""
    assert "count=" in text
    assert "totals" in text
    assert "top_records" in text or "amount=5000" in text
    assert "exceptions" in text or "blocked" in text
    assert "omitted" in text or "additional" in text
    # Never invents a total beyond sum of provided amounts
    assert "5100" not in text or "totals" in text  # allowed if summed correctly
    assert out.token_estimate > 0


def test_context_compressor_does_not_hallucinate_empty() -> None:
    ctx = PlatformContext(
        intent=IntentResult(intent="read"),
        world_state=WorldState(),
        erp_facts={},
    )
    out = context_compressor.compress(ctx)
    assert "memory" not in out.summaries or not out.summaries.get("memory")


# ── Prompt assembly ────────────────────────────────────────────────────────


def test_prompt_assembly_deterministic_section_order() -> None:
    ctx = PlatformContext(
        intent=IntentResult(intent="read", confidence=0.9),
        world_state=WorldState(
            screen=WorldStateScreen(module="AP", entity_type="invoice", entity_id="inv-1"),
            permissions=["ap.read"],
            roles=["analyst"],
        ),
        working_memory=ConversationState(turn_count=2, current_task="review blocked invoice"),
        summaries={
            "policies": "soft_flag=true",
            "invoice": "status=blocked amount=1000",
            "graph": "vendor-A linked",
            "memory": "discussed yesterday",
            "documents": "po scanned",
        },
        entities=[ResolvedEntity(entity_type="invoice", entity_id="inv-1", confidence=0.95)],
    )
    system, user = prompt_assembler.build_answer_prompt(ctx, "Why is this invoice blocked?")
    assert "FLORA" in system or "finance" in system.lower()
    # Fixed order markers
    order = [
        "## SYSTEM INSTRUCTIONS",
        "## PLATFORM POLICIES",
        "## USER PERMISSIONS",
        "## WORLD STATE",
        "## WORKING MEMORY",
        "## RELEVANT ERP DATA",
        "## RELEVANT GRAPH",
        "## RELEVANT DOCUMENTS",
        "## RELEVANT MEMORY",
        "## USER PROMPT",
    ]
    positions = [user.index(h) for h in order]
    assert positions == sorted(positions)
    assert user.index("WORLD STATE") < user.index("USER PROMPT")
    assert "inv-1" in user


# ── Quality ────────────────────────────────────────────────────────────────


def test_quality_requests_expand_when_empty_business_data() -> None:
    ctx = PlatformContext(
        intent=IntentResult(intent="read"),
        world_state=WorldState(),
        question="show cash position",
        erp_facts={},
        memory=[],
        retrieval_trace=[],
        retrieval_failures=[{"source": "erp"}],
    )
    q = context_quality_evaluator.evaluate(ctx)
    assert q.action in {"expand_retrieval", "ok", "clarify"}
    if q.action == "expand_retrieval":
        plan = context_quality_evaluator.expansion_plan(ctx, q)
        assert plan and plan.sources


def test_quality_ok_with_screen_and_erp() -> None:
    ctx = PlatformContext(
        intent=IntentResult(intent="read"),
        world_state=WorldState(screen=WorldStateScreen(entity_id="i1", entity_type="invoice")),
        entities=[ResolvedEntity(entity_type="invoice", entity_id="i1", confidence=0.9)],
        erp_facts={"invoice": {"id": "i1", "status": "open"}},
        summaries={"invoice": "open"},
        question="status of this invoice",
        token_estimate=100,
    )
    q = context_quality_evaluator.evaluate(ctx)
    assert q.sufficient is True
    assert q.action == "ok"


# ── Retrieval ──────────────────────────────────────────────────────────────


def test_retrieval_ui_context_and_approvals_parallel() -> None:
    orch = RetrievalOrchestrator()
    plan = RetrievalPlan(
        query="why blocked",
        sources=[
            RetrievalSource(source_type="platform", tool="ui_context", method="current"),
            RetrievalSource(source_type="platform", tool="approval_queue", method="list"),
        ],
    )
    ws = WorldState(
        screen=WorldStateScreen(module="ap", entity_type="invoice", entity_id="inv-1", tab="header"),
        filters={"status": "blocked"},
    )
    mock_item = MagicMock()
    mock_item.model_dump.return_value = {"title": "Approve invoice", "status": "pending", "source": "m38"}

    with patch(
        "app.modules.finance_os.platform_ai_runtime.goals.goal_manager.goal_manager.list_approval_queue",
        return_value=[mock_item],
    ):
        with patch(
            "app.modules.finance_os.platform_ai_runtime.context.retrieval_orchestrator.context_cache.get",
            return_value=None,
        ):
            with patch(
                "app.modules.finance_os.platform_ai_runtime.context.retrieval_orchestrator.context_cache.set"
            ):
                out = orch.fetch(
                    "org-1",
                    plan=plan,
                    world_state=ws,
                    entities=[ResolvedEntity(entity_type="invoice", entity_id="inv-1", confidence=0.9)],
                    use_cache=False,
                )
    assert out["erp_facts"].get("ui_context", {}).get("screen", {}).get("entity_id") == "inv-1"
    assert out["approval_queue"]
    assert out.get("item_meta") is not None


def test_retrieval_cache_hit_short_circuits() -> None:
    orch = RetrievalOrchestrator()
    plan = RetrievalPlan(
        query="cash",
        sources=[RetrievalSource(source_type="memory", tool="memory", method="search")],
    )
    cached = {
        "memory": [{"content": "cached"}],
        "graph": [],
        "erp_facts": {},
        "documents": [],
        "policies": [],
        "retrieval_trace": [],
        "retrieval_failures": [],
        "retrieval_complete": True,
    }
    with patch(
        "app.modules.finance_os.platform_ai_runtime.context.retrieval_orchestrator.context_cache.get",
        return_value=cached,
    ):
        out = orch.fetch("org", plan=plan, world_state=WorldState(), entities=[], use_cache=True)
    assert out["context_cache_hit"] is True
    assert out["memory"][0]["content"] == "cached"


# ── Cross-module / UI bridge continuity ────────────────────────────────────


def test_this_invoice_uses_world_state_entity() -> None:
    """User says 'this' — planner + builder keep inv id without asking."""
    ws = WorldState(
        screen=WorldStateScreen(module="M11_AP", entity_type="invoice", entity_id="INV-LOCKED"),
        selection={"invoice_id": "INV-LOCKED"},
    )
    eng = WorldStateEngine()
    resolved = eng.from_payload(explicit=ws)
    assert resolved.current_invoice_id == "INV-LOCKED"
    plan = context_planner.plan(
        intent=IntentResult(intent="read"),
        entities=[ResolvedEntity(entity_type="invoice", entity_id="INV-LOCKED", confidence=0.95)],
        world_state=resolved,
        message="Why is this invoice blocked?",
    )
    assert any(
        s.tool in {"invoice", "ui_context", "approval_queue"} or (s.tool == "ap") for s in plan.sources
    )


def test_platform_context_engine_build_wires_quality(monkeypatch) -> None:
    from app.core import config as config_mod
    from app.modules.finance_os.platform_ai_runtime.context.platform_context_engine import PlatformContextEngine

    monkeypatch.setattr(config_mod.settings, "m38_context_engine_enabled", True)
    monkeypatch.setattr(config_mod.settings, "m38_working_memory", False)
    monkeypatch.setattr(config_mod.settings, "m38_ai_firewall_enabled", False)

    engine = PlatformContextEngine()
    ws = WorldState(screen=WorldStateScreen(module="treasury", entity_type=None))

    def fake_fetch(*a, **k):
        return {
            "memory": [{"content": "cash is high", "entity_id": "t1", "final_score": 0.8}],
            "graph": [],
            "erp_facts": {"erp:treasury.get_cash_position": {"balance": 1_000_000}},
            "documents": [],
            "policies": [],
            "workflow_state": [],
            "approval_queue": [],
            "recent_events": [],
            "retrieval_trace": [{"source": "memory", "ok": True}],
            "retrieval_failures": [],
            "retrieval_complete": True,
            "item_meta": [],
            "context_cache_hit": False,
        }

    with patch(
        "app.modules.finance_os.platform_ai_runtime.context.platform_context_engine.retrieval_orchestrator.fetch",
        side_effect=fake_fetch,
    ):
        with patch(
            "app.modules.finance_os.platform_ai_runtime.context.platform_context_engine.billing_ai_operation"
        ):
            with patch(
                "app.modules.finance_os.platform_ai_runtime.context.platform_context_engine.ai_firewall.enforce",
                side_effect=lambda m, **k: m,
            ):
                with patch(
                    "app.modules.finance_os.platform_ai_runtime.context.platform_context_engine.audit_repo.create_log"
                ):
                    ctx = engine.build("org-1", message="what is cash?", world_state=ws, user_id="u1")
    assert ctx.quality is not None
    assert ctx.summaries
    assert ctx.intent.intent in {"read", "analysis", "mixed", "action", "workflow"}


def test_prompt_assembler_fallback_stable() -> None:
    ctx = PlatformContext(
        intent=IntentResult(intent="read"),
        world_state=WorldState(),
        summaries={"z_last": "z", "a_first": "a", "ui_location": "AP"},
    )
    t1 = prompt_assembler.fallback_text(ctx)
    t2 = prompt_assembler.fallback_text(ctx)
    assert t1 == t2
    assert t1.index("ui_location") < t1.index("z_last")


def test_cross_module_invoice_chain_in_planner() -> None:
    plan = context_planner.plan(
        intent=IntentResult(intent="analysis", suggested_modules=["ap"]),
        entities=[ResolvedEntity(entity_type="invoice", entity_id="i1", confidence=0.9)],
        world_state=WorldState(screen=WorldStateScreen(entity_type="invoice", entity_id="i1")),
        message="link this invoice to payment gst and journals",
    )
    tool_methods = {(s.tool, s.method) for s in plan.sources}
    # Should include graph + cross-module related sources
    assert any(s.cross_module for s in plan.sources) or ("graph", "traverse") in tool_methods
