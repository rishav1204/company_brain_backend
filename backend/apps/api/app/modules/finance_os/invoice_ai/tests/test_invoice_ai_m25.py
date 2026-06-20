from __future__ import annotations

from app.modules.finance_os.invoice_ai.ai.invoice_extractor import extract_regex
from app.modules.finance_os.invoice_ai.ai.entity_normalizer import normalize_gstin, normalize_vendor_name
from app.modules.finance_os.invoice_ai.ai.duplicate_scorer import classify_duplicate_status, weighted_duplicate_score
from app.modules.finance_os.invoice_ai.ai.anomaly_detector import detect_anomalies
from app.modules.finance_os.invoice_ai.ai.confidence_scorer import auto_draft_eligible, confidence_band, overall_confidence
from app.modules.finance_os.invoice_ai.ai.gst_predictor import predict_gst_code
from app.modules.finance_os.invoice_ai.ai.ledger_predictor import score_ledger_match, suggest_from_patterns


SAMPLE_TEXT = """
Tax Invoice
Invoice No: INV-2024-001
From: Acme Supplies Pvt Ltd
GSTIN: 27AABCU9603R1ZM
Date: 15-01-2024
Taxable: 10000
CGST: 900
SGST: 900
Grand Total: 11800
"""


def test_regex_extract_invoice_number() -> None:
    result = extract_regex(SAMPLE_TEXT)
    assert result["invoice_number"] == "INV-2024-001"


def test_regex_extract_gstin() -> None:
    result = extract_regex(SAMPLE_TEXT)
    assert result["vendor_gstin"] == "27AABCU9603R1ZM"


def test_regex_extract_total() -> None:
    result = extract_regex(SAMPLE_TEXT)
    assert result["total_amount"] == 11800.0


def test_regex_extract_vendor() -> None:
    result = extract_regex(SAMPLE_TEXT)
    assert "Acme" in str(result.get("vendor_name") or "")


def test_regex_confidence_positive() -> None:
    result = extract_regex(SAMPLE_TEXT)
    assert float(result["extraction_confidence"]) > 0.5


def test_regex_empty_text() -> None:
    result = extract_regex("")
    assert result["total_amount"] == 0


def test_normalize_vendor_name() -> None:
    assert normalize_vendor_name("  Acme Supplies  ") == "ACME SUPPLIES"


def test_normalize_vendor_none() -> None:
    assert normalize_vendor_name(None) is None


def test_normalize_gstin() -> None:
    assert normalize_gstin("27aabcu9603r1zm") == "27AABCU9603R1ZM"


def test_duplicate_score_full_match() -> None:
    score, breakdown = weighted_duplicate_score(
        invoice_number_match=True,
        vendor_match=True,
        amount_delta_pct=0.0,
        date_delta_days=1,
    )
    assert score >= 90
    assert breakdown["total"] >= 90


def test_duplicate_score_no_match() -> None:
    score, _ = weighted_duplicate_score(
        invoice_number_match=False,
        vendor_match=False,
        amount_delta_pct=0.5,
        date_delta_days=30,
    )
    assert score < 60


def test_duplicate_score_invoice_only() -> None:
    score, _ = weighted_duplicate_score(
        invoice_number_match=True,
        vendor_match=False,
        amount_delta_pct=0.5,
        date_delta_days=None,
    )
    assert score == 40


def test_duplicate_score_vendor_only() -> None:
    score, _ = weighted_duplicate_score(
        invoice_number_match=False,
        vendor_match=True,
        amount_delta_pct=0.5,
        date_delta_days=None,
    )
    assert score == 25


def test_duplicate_status_clean() -> None:
    assert classify_duplicate_status(30) == "clean"


def test_duplicate_status_suspected() -> None:
    assert classify_duplicate_status(70) == "suspected"


def test_duplicate_status_confirmed() -> None:
    assert classify_duplicate_status(95) == "confirmed"


def test_anomaly_low_confidence() -> None:
    items = detect_anomalies(
        total_amount=1000,
        vendor_avg=1000,
        vendor_std=100,
        extraction_confidence=0.3,
        duplicate_status="clean",
    )
    assert any(i["anomaly_type"] == "low_extraction_confidence" for i in items)


def test_anomaly_duplicate() -> None:
    items = detect_anomalies(
        total_amount=1000,
        vendor_avg=1000,
        vendor_std=100,
        extraction_confidence=0.9,
        duplicate_status="confirmed",
    )
    assert any(i["anomaly_type"] == "duplicate_invoice" for i in items)


def test_anomaly_amount_spike() -> None:
    items = detect_anomalies(
        total_amount=50000,
        vendor_avg=5000,
        vendor_std=500,
        extraction_confidence=0.9,
        duplicate_status="clean",
    )
    assert any(i["anomaly_type"] == "amount_spike" for i in items)


def test_anomaly_clean() -> None:
    items = detect_anomalies(
        total_amount=5000,
        vendor_avg=5000,
        vendor_std=500,
        extraction_confidence=0.9,
        duplicate_status="clean",
    )
    assert len(items) == 0


def test_confidence_band_auto_suggest() -> None:
    assert confidence_band(96) == "auto_suggest"


def test_confidence_band_review() -> None:
    assert confidence_band(85) == "review_suggested"


def test_confidence_band_manual() -> None:
    assert confidence_band(70) == "manual_review"


def test_confidence_band_human() -> None:
    assert confidence_band(40) == "human_entry"


def test_overall_confidence_high() -> None:
    score = overall_confidence(95, [90, 85], "clean", 0)
    assert score >= 80


def test_overall_confidence_duplicate_penalty() -> None:
    clean = overall_confidence(95, [90], "clean", 0)
    confirmed = overall_confidence(95, [90], "confirmed", 0)
    assert confirmed < clean


def test_auto_draft_eligible() -> None:
    assert auto_draft_eligible(85, "clean", 0) is True


def test_auto_draft_blocked_duplicate() -> None:
    assert auto_draft_eligible(95, "suspected", 0) is False


def test_auto_draft_blocked_anomaly() -> None:
    assert auto_draft_eligible(95, "clean", 1) is False


def test_gst_predict_18_percent() -> None:
    result = predict_gst_code(vendor_gstin="27AABCU9603R1ZM", taxable_amount=10000, gst_amount=1800)
    assert "18" in result["suggested_gst_code"]


def test_gst_predict_exempt() -> None:
    result = predict_gst_code(vendor_gstin=None, taxable_amount=1000, gst_amount=0)
    assert result["suggested_gst_code"] == "EXEMPT"


def test_ledger_score_vendor_history() -> None:
    score = score_ledger_match(
        account_code="5000",
        account_name="Expense",
        vendor_history_account="5000",
        retrieval_score=0.5,
    )
    assert score >= 0.65


def test_ledger_suggest_from_patterns() -> None:
    patterns = [{"score": 0.8, "metadata": {"account_code": "5100", "account_name": "IT Expense"}}]
    result = suggest_from_patterns(patterns)
    assert result is not None
    assert result["account_code"] == "5100"


def test_ledger_suggest_vendor_history_fallback() -> None:
    result = suggest_from_patterns([], vendor_account="5200")
    assert result is not None
    assert result["source"] == "vendor_history"


def test_ledger_suggest_empty() -> None:
    assert suggest_from_patterns([]) is None


def test_events_module_exports() -> None:
    from app.modules.finance_os.invoice_ai.events import invoice_ai_events

    assert invoice_ai_events.INVOICE_EXTRACTED == "invoice.extracted"
    assert invoice_ai_events.INVOICE_PREDICTED == "invoice.predicted"


def test_schema_extract_response() -> None:
    from app.modules.finance_os.invoice_ai.schemas.invoice_ai_schema import ExtractResponse

    r = ExtractResponse(extraction_id="e1", document_id="d1")
    assert r.confidence_band == "manual_review"


def test_schema_pipeline_result() -> None:
    from app.modules.finance_os.invoice_ai.schemas.invoice_ai_schema import PipelineResult

    r = PipelineResult(extraction_id="e1", document_id="d1", confidence_band="review_suggested")
    assert r.auto_draft_eligible is False


def test_guard_read_ap_permission() -> None:
    from app.modules.finance_os.invoice_ai.security.invoice_ai_guard import require_invoice_ai_read

    require_invoice_ai_read({"permissions": ["ap.read"]})


def test_guard_write_ap_permission() -> None:
    from app.modules.finance_os.invoice_ai.security.invoice_ai_guard import require_invoice_ai_write

    require_invoice_ai_write({"permissions": ["ap.write"]})


def test_ar_hook_stub() -> None:
    from app.modules.erp.accounts_receivable.services import ar_invoice_ai_hook

    assert callable(ar_invoice_ai_hook.process_sales_document)


def test_platform_extractor_delegates() -> None:
    from app.modules.platform.documents.ai.invoice_extractor import invoice_extractor

    result = invoice_extractor.extract(SAMPLE_TEXT)
    assert result["total_amount"] > 0


def test_platform_ledger_suggester_fallback() -> None:
    from app.modules.platform.documents.ai.ledger_suggester import suggest_ledger_accounts

    items = suggest_ledger_accounts({"total_amount": 1000})
    assert len(items) >= 1


def test_duplicate_amount_partial_match() -> None:
    score, _ = weighted_duplicate_score(
        invoice_number_match=False,
        vendor_match=True,
        amount_delta_pct=0.03,
        date_delta_days=5,
    )
    assert 40 <= score <= 60


def test_duplicate_date_proximity() -> None:
    score_near, _ = weighted_duplicate_score(
        invoice_number_match=True,
        vendor_match=True,
        amount_delta_pct=0.0,
        date_delta_days=3,
    )
    score_far, _ = weighted_duplicate_score(
        invoice_number_match=True,
        vendor_match=True,
        amount_delta_pct=0.0,
        date_delta_days=30,
    )
    assert score_near > score_far


def test_confidence_anomaly_penalty() -> None:
    no_anom = overall_confidence(90, [85], "clean", 0)
    with_anom = overall_confidence(90, [85], "clean", 2)
    assert with_anom < no_anom


def test_gst_inter_state() -> None:
    result = predict_gst_code(
        vendor_gstin="29AABCU9603R1ZM",
        taxable_amount=1000,
        gst_amount=180,
        state_code="27",
    )
    assert "IGST" in result["suggested_gst_code"]


def test_regex_multiple_dates() -> None:
    text = "Invoice Date: 01-02-2024 Due: 15-02-2024 Total: 500"
    result = extract_regex(text)
    assert result["invoice_date"] is not None


def test_normalize_vendor_special_chars() -> None:
    assert normalize_vendor_name("Foo & Bar (India)") == "FOO & BAR INDIA"


def test_anomaly_suspected_duplicate() -> None:
    items = detect_anomalies(
        total_amount=1000,
        vendor_avg=1000,
        vendor_std=100,
        extraction_confidence=0.9,
        duplicate_status="suspected",
    )
    assert any(i["severity"] == "medium" for i in items)
