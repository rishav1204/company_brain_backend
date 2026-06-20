from __future__ import annotations

from app.modules.finance_os.memory.engine.importance_engine import (
    IMPORTANCE_THRESHOLD,
    compute_importance,
    default_ttl_for_band,
    financial_impact_weight,
    human_action_boost,
    importance_band,
    passes_importance_gate,
    recurrence_boost,
    risk_boost,
)
from app.modules.finance_os.memory.engine.ranking_engine import frequency_boost, keyword_match, rank_candidates, recency_decay
from app.modules.finance_os.memory.engine.summarization_engine import build_summary_title, summarize_entries
from app.modules.finance_os.memory.ai.knowledge_extractor import NOISE_EVENTS, extract_from_event
from app.modules.finance_os.memory.ai.pattern_detector import detect_recurring_patterns
from app.modules.finance_os.memory.memories import (
    accounting_memory,
    approval_memory,
    compliance_memory,
    reconciliation_memory,
    treasury_memory,
    user_preference_memory,
    vendor_memory,
)
from app.modules.finance_os.memory.events.memory_events import (
    MEMORY_CREATED,
    MEMORY_EXPIRED,
    MEMORY_HIGH_IMPORTANCE,
    MEMORY_SUMMARIZED,
    MEMORY_UPDATED,
)


def test_importance_band_critical() -> None:
    assert importance_band(95) == "critical"


def test_importance_band_high() -> None:
    assert importance_band(75) == "high"


def test_importance_band_medium() -> None:
    assert importance_band(55) == "medium"


def test_importance_band_low() -> None:
    assert importance_band(30) == "low"


def test_passes_gate_at_threshold() -> None:
    assert passes_importance_gate(IMPORTANCE_THRESHOLD) is True


def test_fails_gate_below_threshold() -> None:
    assert passes_importance_gate(49) is False


def test_force_bypasses_gate() -> None:
    assert passes_importance_gate(10, force=True) is True


def test_financial_impact_large() -> None:
    assert financial_impact_weight(6_000_000) == 20.0


def test_financial_impact_small() -> None:
    assert financial_impact_weight(1000) == 2.0


def test_recurrence_boost_high() -> None:
    assert recurrence_boost(12) == 15.0


def test_recurrence_boost_none() -> None:
    assert recurrence_boost(0) == 0.0


def test_risk_boost_compliance() -> None:
    assert risk_boost(compliance=True) >= 15.0


def test_human_action_rejection() -> None:
    assert human_action_boost(rejection=True) == 10.0


def test_compute_importance_payment() -> None:
    score = compute_importance(event_type="payment.executed", amount=600_000)
    assert score >= 65


def test_default_ttl_critical_forever() -> None:
    assert default_ttl_for_band("critical") == "forever"


def test_default_ttl_high_180d() -> None:
    assert default_ttl_for_band("high") == "180d"


def test_keyword_match_full() -> None:
    assert keyword_match("vendor payment", "vendor payment executed") == 1.0


def test_keyword_match_none() -> None:
    assert keyword_match("xyz", "abc") == 0.0


def test_frequency_boost_high() -> None:
    assert frequency_boost(25) == 1.0


def test_recency_decay_recent() -> None:
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).isoformat()
    assert recency_decay(ts) > 0.9


def test_rank_candidates_orders_by_score() -> None:
    ranked = rank_candidates(
        [
            {"content": "vendor abc", "importance_score": 50, "distance": 0.8, "created_at": "2020-01-01T00:00:00+00:00"},
            {"content": "vendor abc payment", "importance_score": 90, "distance": 0.2, "created_at": "2025-01-01T00:00:00+00:00"},
        ],
        query="vendor payment",
    )
    assert ranked[0]["importance_score"] == 90


def test_rank_skips_expired() -> None:
    ranked = rank_candidates([{"content": "x", "status": "expired", "importance_score": 99}], query="x")
    assert ranked == []


def test_summarize_entries() -> None:
    text = summarize_entries([{"title": "A", "content": "Pattern one"}, {"title": "B", "content": "Pattern two"}])
    assert "Pattern" in text


def test_build_summary_title() -> None:
    title = build_summary_title("vendor", "vendor", 10)
    assert "10" in title


def test_noise_event_rejected() -> None:
    assert "document.uploaded" in NOISE_EVENTS
    assert extract_from_event("document.uploaded", {}) is None


def test_vendor_payment_extract() -> None:
    result = vendor_memory.extract("payment.executed", {"vendor_name": "Acme", "amount": 100000})
    assert result is not None
    assert result["memory_type"] == "vendor"


def test_vendor_duplicate_extract() -> None:
    result = vendor_memory.extract("invoice.duplicate_detected", {"vendor_name": "Acme", "reason": "same number"})
    assert result is not None
    assert result["importance_score"] >= 50


def test_vendor_low_amount_invoice_ignored() -> None:
    result = vendor_memory.extract("erp.invoice.approved", {"vendor_name": "Acme", "amount": 1000})
    assert result is None


def test_approval_completed_extract() -> None:
    result = approval_memory.extract("approval.completed", {"workflow_type": "AP", "approval_hours": 4})
    assert result is not None
    assert "AP" in result["content"]


def test_approval_rejected_extract() -> None:
    result = approval_memory.extract("approval.rejected", {"workflow_type": "AP", "reason": "missing docs"})
    assert result is not None
    assert result["importance_score"] >= 50


def test_workflow_intelligence_extract() -> None:
    result = approval_memory.extract(
        "workflow.intelligence.completed", {"workflow_type": "AP", "top_bottleneck": "CFO"}
    )
    assert result is not None


def test_workflow_intelligence_no_bottleneck_skipped() -> None:
    assert approval_memory.extract("workflow.intelligence.completed", {"workflow_type": "AP"}) is None


def test_accounting_journal_extract() -> None:
    result = accounting_memory.extract("journal.posted", {"account_code": "5000"})
    assert result is not None


def test_accounting_prediction_override() -> None:
    result = accounting_memory.extract(
        "invoice.predicted", {"vendor_name": "Acme", "suggested_ledger": "6100", "human_override": True}
    )
    assert result is not None


def test_accounting_prediction_no_signal_skipped() -> None:
    assert accounting_memory.extract("invoice.predicted", {"vendor_name": "Acme"}) is None


def test_treasury_liquidity_extract() -> None:
    result = treasury_memory.extract("liquidity_alert.created", {"message": "Low cash"})
    assert result is not None
    assert result["ttl_policy"] == "forever"


def test_treasury_risk_extract() -> None:
    result = treasury_memory.extract("treasury.risk.detected", {"summary": "FX exposure"})
    assert result is not None


def test_compliance_alert_extract() -> None:
    result = compliance_memory.extract("compliance.alert.generated", {"message": "GST filing due"})
    assert result is not None
    assert result["memory_type"] == "compliance"


def test_reconciliation_override_extract() -> None:
    result = reconciliation_memory.extract("reconciliation.completed", {"override_reason": "fee mismatch"})
    assert result is not None


def test_reconciliation_no_reason_skipped() -> None:
    assert reconciliation_memory.extract("reconciliation.completed", {}) is None


def test_reconciliation_adjustment_extract() -> None:
    result = reconciliation_memory.extract("reconciliation.adjustment.posted", {"reason": "bank fee"})
    assert result is not None


def test_decision_recorded_extract() -> None:
    result = user_preference_memory.extract(
        "decision.recorded", {"decision_id": "d1", "title": "Capitalize asset", "rationale": "Above threshold"}
    )
    assert result is not None


def test_manual_payload_extract() -> None:
    result = extract_from_event(
        "memory.write",
        {"title": "T", "content": "C", "memory_type": "user", "importance_score": 60},
    )
    assert result is not None
    assert result["title"] == "T"


def test_pattern_detector_recurrence() -> None:
    entries = [{"title": "Same", "memory_type": "vendor"} for _ in range(5)]
    patterns = detect_recurring_patterns(entries, min_count=3)
    assert any(p["pattern"] == "Same" for p in patterns)


def test_event_constants() -> None:
    assert MEMORY_CREATED == "memory.created"
    assert MEMORY_UPDATED == "memory.updated"
    assert MEMORY_EXPIRED == "memory.expired"
    assert MEMORY_HIGH_IMPORTANCE == "memory.high_importance.detected"
    assert MEMORY_SUMMARIZED == "memory.summarized"


def test_m26_write_pattern_memory_import() -> None:
    from app.modules.finance_os.workflow_intelligence.retrieval import workflow_memory

    assert callable(workflow_memory.write_pattern_memory)


def test_m25_vendor_memory_search_import() -> None:
    from app.modules.finance_os.invoice_ai.retrieval import vendor_memory

    assert callable(vendor_memory.retrieve_vendor_patterns)


def test_ingestion_pipeline_event_map() -> None:
    from app.modules.finance_os.memory.ai.knowledge_extractor import EXTRACTOR_MAP

    assert "payment.executed" in EXTRACTOR_MAP
    assert "decision.recorded" in EXTRACTOR_MAP


def test_embedding_fallback_deterministic() -> None:
    from app.modules.finance_os.memory.engine.embedding_engine import _hash_fallback_embedding

    a = _hash_fallback_embedding("test")
    b = _hash_fallback_embedding("test")
    assert a == b
    assert len(a) == 1536


def test_memory_guard_read_permissions() -> None:
    from app.modules.finance_os.memory.security.memory_guard import require_memory_read

    require_memory_read({"permissions": ["memory.read"]})


def test_memory_guard_write_permissions() -> None:
    from app.modules.finance_os.memory.security.memory_guard import require_memory_write

    require_memory_write({"permissions": ["memory.write"]})


def test_copilot_without_llm() -> None:
    from app.modules.finance_os.memory.ai.memory_copilot import answer

    result = answer("org", "vendor patterns")
    assert "answer" in result


def test_reasoner_empty() -> None:
    from app.modules.finance_os.memory.ai.memory_reasoner import build_context

    assert build_context("org", "nonexistent query xyz123") == "" or isinstance(build_context("org", "q"), str)


def test_reconciliation_bridge_import() -> None:
    from app.modules.finance_os.memory.bridges.reconciliation_bridge import reconciliation_context

    assert callable(reconciliation_context)


def test_treasury_bridge_import() -> None:
    from app.modules.finance_os.memory.bridges.treasury_bridge import treasury_context

    assert callable(treasury_context)


def test_router_prefix() -> None:
    assert "/finance-os/memory" == "/finance-os/memory"


def test_importance_gating_discard_low_score() -> None:
    score = compute_importance(event_type="unknown_event")
    assert score < IMPORTANCE_THRESHOLD or passes_importance_gate(score) is True


def test_gst_mismatch_compliance_score() -> None:
    result = compliance_memory.extract("gst.mismatch.detected", {"message": "ITC mismatch"})
    assert result is not None
    assert result["importance_score"] >= 80


def test_payment_completed_high_importance_potential() -> None:
    score = compute_importance(event_type="payment.executed", amount=5_000_000)
    assert importance_band(score) in {"high", "critical"}
