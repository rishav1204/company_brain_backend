from __future__ import annotations

from app.modules.erp.reconciliation.engine.matching_engine import rank_all_candidates, score_match
from app.modules.erp.reconciliation.engine.fuzzy_matching_engine import narration_similarity, counterparty_fuzzy
from app.modules.erp.reconciliation.engine.confidence_engine import compute_confidence, score_to_band, load_weights
from app.modules.erp.reconciliation.engine.settlement_engine import allocate_partial, build_match_lines, group_status
from app.modules.erp.reconciliation.engine.anomaly_engine import detect_reconciliation_anomalies
from app.modules.erp.reconciliation.ai.suggestion_engine import suggest_matches
from app.modules.erp.reconciliation.ai.confidence_scorer import score_breakdown
from app.modules.erp.reconciliation.ai.reconciliation_copilot import answer_reconciliation_question
from app.modules.erp.reconciliation.ai.transaction_classifier import classify_narration
from app.modules.erp.reconciliation.validators.match_validator import validate_match_request
from app.modules.erp.reconciliation.validators.approval_validator import validate_approve_status, validate_reject_status


def _bank_tx(**kwargs):
    return {"amount": 1000, "transaction_date": "2025-06-01", "transaction_reference": "INV-1001", "description": "ABC INDUSTRIES", "transaction_type": "credit", **kwargs}


def test_score_exact_amount() -> None:
    r = score_match(bank_amount=1000, bank_date="2025-06-01", bank_reference="INV-1001", bank_description="pay", bank_counterparty="", ledger_debit=0, ledger_credit=1000, ledger_date="2025-06-01", ledger_reference="INV-1001")
    assert r["confidence_score"] >= 0.8


def test_score_source_id_fast_path() -> None:
    r = score_match(bank_amount=1000, bank_date="2025-06-01", bank_reference="", bank_description="", bank_counterparty="", ledger_debit=0, ledger_credit=1000, ledger_date="2025-06-01", ledger_reference="", source_id="abc", candidate_id="abc")
    assert r["confidence_score"] == 1.0


def test_score_low_is_exception() -> None:
    r = score_match(bank_amount=100, bank_date="2025-01-01", bank_reference="", bank_description="", bank_counterparty="", ledger_debit=0, ledger_credit=9999, ledger_date="2025-12-01", ledger_reference="")
    assert r["match_type"] == "exception"


def test_rank_subledger_direction() -> None:
    bank = _bank_tx(transaction_type="credit")
    cands = [{"id": "1", "target_type": "ar_receipt", "amount": 1000, "date": "2025-06-01", "reference": "INV-1001"}]
    ranked = rank_all_candidates(bank, [], cands)
    assert ranked[0]["match_target_type"] == "ar_receipt"


def test_narration_similarity() -> None:
    assert narration_similarity("ABC INDUSTRIES PAYMENT", "ABC Industries Pvt Ltd") >= 0.3


def test_counterparty_fuzzy() -> None:
    assert counterparty_fuzzy("Payment to ABC Industries", "ABC Industries") >= 0.5


def test_confidence_band_auto() -> None:
    assert score_to_band(97) == "auto_suggest"


def test_confidence_band_manual() -> None:
    assert score_to_band(50) == "manual"


def test_compute_confidence_source() -> None:
    r = compute_confidence({"source_id_match": True})
    assert r["confidence_100"] == 100


def test_load_weights_defaults() -> None:
    w = load_weights(None)
    assert w["amount_exact"] == 40.0


def test_allocate_partial() -> None:
    r = allocate_partial(invoice_amount=100000, payment_amount=60000)
    assert r["status"] == "partially_matched"
    assert r["remaining_amount"] == 40000


def test_allocate_full() -> None:
    r = allocate_partial(invoice_amount=1000, payment_amount=1000)
    assert r["status"] == "matched"


def test_build_match_lines() -> None:
    lines = build_match_lines(reconciliation_id="r1", bank_transaction_id="t1", allocations=[{"entity_type": "ar_invoice", "entity_id": "i1", "amount": 500, "invoice_amount": 1000}])
    assert len(lines) == 1
    assert lines[0]["remaining_amount"] == 500


def test_group_status_partial() -> None:
    assert group_status([{"remaining_amount": 100}]) == "partially_matched"


def test_group_status_matched() -> None:
    assert group_status([{"remaining_amount": 0}]) == "matched"


def test_anomaly_large() -> None:
    flags = detect_reconciliation_anomalies(bank_tx={"amount": 600000, "transaction_reference": "", "description": ""})
    assert any(f["type"] == "large_transfer" for f in flags)


def test_anomaly_reference_missing() -> None:
    flags = detect_reconciliation_anomalies(bank_tx={"amount": 100, "transaction_reference": "", "description": "x"})
    assert any(f["type"] == "reference_missing" for f in flags)


def test_suggest_matches_ai_flag() -> None:
    bank = _bank_tx()
    ledger = [{"id": "l1", "debit_amount": 0, "credit_amount": 1000, "posting_date": "2025-06-01", "reference_id": "INV-1001"}]
    items = suggest_matches(bank, ledger, limit=1)
    assert items[0]["ai_suggestion"] is True


def test_score_breakdown() -> None:
    b = score_breakdown({"confidence_score": 0.95, "confidence_100": 95, "band": "auto_suggest", "factors": ["amount_exact"]})
    assert "recommendation" in b


def test_copilot_unreconciled() -> None:
    ans = answer_reconciliation_question(question="why unreconciled", unreconciled=[{"amount": 1000, "transaction_date": "2025-06-01", "transaction_reference": "R1"}])
    assert "unreconciled" in ans["answer"].lower()


def test_copilot_manual_review() -> None:
    ans = answer_reconciliation_question(question="manual review", suggestions=[{"confidence_score": 0.5}])
    assert "manual" in ans["answer"].lower() or "review" in ans["answer"].lower()


def test_classify_salary() -> None:
    assert classify_narration("SALARY NEFT") == "payroll"


def test_classify_bank_charge() -> None:
    assert classify_narration("BANK CHARGE") == "bank_charge"


def test_validate_match_request_ok() -> None:
    validate_match_request(bank_transaction_ids=["t1"], allocations=[{"entity_type": "ar_receipt", "entity_id": "r1", "amount": 100}])


def test_validate_match_request_fail() -> None:
    try:
        validate_match_request(bank_transaction_ids=[], allocations=[])
        assert False
    except ValueError:
        assert True


def test_validate_approve_suggested() -> None:
    validate_approve_status("suggested")


def test_validate_approve_matched_fail() -> None:
    try:
        validate_approve_status("matched")
        assert False
    except ValueError:
        assert True


def test_validate_reject_suggested() -> None:
    validate_reject_status("suggested")


def test_treasury_reexports_engine() -> None:
    from app.modules.erp.treasury.engine.reconciliation_engine import score_match as treasury_score
    from app.modules.erp.reconciliation.engine.matching_engine import score_match as recon_score
    assert treasury_score is recon_score


def test_treasury_reexports_service() -> None:
    from app.modules.erp.treasury.services.reconciliation_service import reconciliation_service as t
    from app.modules.erp.reconciliation.services.reconciliation_service import reconciliation_service as r
    assert t is r


def test_reconciliation_events_exist() -> None:
    from app.modules.erp.reconciliation.events import reconciliation_events
    assert callable(reconciliation_events.emit_reconciliation_suggested)


def test_exception_service_module() -> None:
    import importlib.util
    assert importlib.util.find_spec("app.modules.erp.reconciliation.services.exception_service") is not None


def test_adjustment_validator() -> None:
    from app.modules.erp.reconciliation.validators.reconciliation_validator import validate_adjustment
    try:
        validate_adjustment(adjustment_type="bad", amount=10, expense_account_id="a", bank_account_id="b")
        assert False
    except ValueError:
        assert True


def test_router_prefix_in_source() -> None:
    from pathlib import Path
    src = Path(__file__).resolve().parents[1] / "routes" / "router.py"
    assert "erp/reconciliation" in src.read_text(encoding="utf-8")


def test_date_proximity_score() -> None:
    r = score_match(bank_amount=1000, bank_date="2025-06-01", bank_reference="", bank_description="", bank_counterparty="", ledger_debit=0, ledger_credit=1000, ledger_date="2025-06-03", ledger_reference="")
    assert "date_close" in r["factors"] or "date_exact" in r["factors"]


def test_amount_near_match() -> None:
    r = score_match(bank_amount=1000, bank_date="2025-06-01", bank_reference="", bank_description="", bank_counterparty="", ledger_debit=0, ledger_credit=1010, ledger_date="2025-06-01", ledger_reference="")
    assert r["confidence_score"] > 0.2


def test_debit_skips_ar_on_credit_tx() -> None:
    bank = _bank_tx(transaction_type="credit")
    cands = [{"id": "1", "target_type": "ap_payment", "amount": 1000, "date": "2025-06-01", "reference": "P1"}]
    ranked = rank_all_candidates(bank, [], cands)
    assert ranked == []


def test_anomaly_duplicate() -> None:
    cands = [{"amount": 100, "reference": "R1"}, {"amount": 100, "reference": "R1"}]
    flags = detect_reconciliation_anomalies(bank_tx={"amount": 100, "transaction_reference": "R1", "description": ""}, candidates=cands)
    assert any(f["type"] == "duplicate_entry" for f in flags)


def test_copilot_exceptions() -> None:
    ans = answer_reconciliation_question(question="show exceptions", exceptions=[{"id": "e1"}])
    assert "exception" in ans["answer"].lower()


def test_confidence_review_band() -> None:
    assert score_to_band(70) == "review"


def test_confidence_likely_band() -> None:
    assert score_to_band(85) == "likely_match"


def test_multi_allocation_lines() -> None:
    lines = build_match_lines(
        reconciliation_id="r1",
        bank_transaction_id="t1",
        allocations=[
            {"entity_type": "ar_invoice", "entity_id": "i1", "amount": 300, "invoice_amount": 300},
            {"entity_type": "ar_invoice", "entity_id": "i2", "amount": 200, "invoice_amount": 200},
        ],
    )
    assert len(lines) == 2


def test_emit_suggested_event_payload() -> None:
    from unittest.mock import patch
    from app.modules.erp.reconciliation.events.reconciliation_events import emit_reconciliation_suggested
    with patch("app.modules.erp.reconciliation.events.reconciliation_events.platform_event_service.publish") as pub:
        emit_reconciliation_suggested("org", reconciliation_id="r1", confidence=0.9)
        assert pub.call_args.kwargs["event_type"] == "reconciliation.suggested"


def test_auto_match_job_import() -> None:
    from app.modules.erp.reconciliation.jobs.auto_match_job import run_auto_match
    assert callable(run_auto_match)


def test_scan_job_import() -> None:
    from app.modules.erp.reconciliation.jobs.reconciliation_scan_job import run_reconciliation_scan
    assert callable(run_reconciliation_scan)


def test_guard_module_exists() -> None:
    import importlib.util
    assert importlib.util.find_spec("app.modules.erp.reconciliation.security.reconciliation_guard") is not None


def test_vendor_match_service_import() -> None:
    from app.modules.erp.reconciliation.services.vendor_match_service import vendor_match_service
    assert callable(vendor_match_service.collect_candidates)


def test_customer_match_service_import() -> None:
    from app.modules.erp.reconciliation.services.customer_match_service import customer_match_service
    assert callable(customer_match_service.collect_candidates)


def test_bank_match_service_import() -> None:
    from app.modules.erp.reconciliation.services.bank_match_service import bank_match_service
    assert callable(bank_match_service.list_workbench)


def test_approval_service_import() -> None:
    from app.modules.erp.reconciliation.services.approval_service import approval_service
    assert callable(approval_service.approve)


def test_adjustment_service_import() -> None:
    from app.modules.erp.reconciliation.services.adjustment_service import adjustment_service
    assert callable(adjustment_service.create)


def test_anomaly_detector_ai_wrapper() -> None:
    from app.modules.erp.reconciliation.ai.anomaly_detector import detect_anomalies
    flags = detect_anomalies(bank_tx={"amount": 100, "transaction_reference": "x", "description": ""})
    assert any(f["type"] == "unknown_beneficiary" for f in flags)


def test_fuzzy_empty() -> None:
    assert narration_similarity("", "") == 0.0


def test_settlement_zero_invoice() -> None:
    r = allocate_partial(invoice_amount=0, payment_amount=100)
    assert r["allocated_amount"] == 0
