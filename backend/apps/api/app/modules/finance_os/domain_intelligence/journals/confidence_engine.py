from __future__ import annotations

DEFAULT_THRESHOLD = 0.85


def score_journal_confidence(*, ledger_confidence: float, gst_confidence: float, vendor_confidence: float) -> dict:
    scores = {
        "ledger_confidence": round(float(ledger_confidence), 4),
        "gst_confidence": round(float(gst_confidence), 4),
        "vendor_confidence": round(float(vendor_confidence), 4),
    }
    overall = min(scores.values()) if scores else 0.0
    scores["overall"] = round(overall, 4)
    scores["requires_review"] = overall < DEFAULT_THRESHOLD
    scores["threshold"] = DEFAULT_THRESHOLD
    return scores


def requires_finance_review(ai_confidence: dict | None) -> bool:
    if not isinstance(ai_confidence, dict):
        return False
    if ai_confidence.get("reviewed_at"):
        return False
    return bool(ai_confidence.get("requires_review"))
