from __future__ import annotations


def confidence_band(score_pct: float) -> str:
    """score_pct is 0-100."""
    if score_pct >= 95:
        return "auto_suggest"
    if score_pct >= 80:
        return "review_suggested"
    if score_pct >= 60:
        return "manual_review"
    return "human_entry"


def overall_confidence(
    extraction_confidence: float,
    prediction_confidences: list[float],
    duplicate_status: str,
    anomaly_count: int,
) -> float:
    """Returns 0-100 confidence."""
    ext = extraction_confidence * 100 if extraction_confidence <= 1 else extraction_confidence
    base = ext
    if prediction_confidences:
        preds = [p * 100 if p <= 1 else p for p in prediction_confidences]
        base = base * 0.5 + (sum(preds) / len(preds)) * 0.5
    if duplicate_status == "confirmed":
        base *= 0.3
    elif duplicate_status == "suspected":
        base *= 0.6
    if anomaly_count > 0:
        base *= max(0.4, 1.0 - anomaly_count * 0.15)
    return round(max(0.0, min(100.0, base)), 2)


def auto_draft_eligible(
    overall: float,
    duplicate_status: str,
    anomaly_count: int,
    *,
    min_confidence: float = 80.0,
) -> bool:
    if duplicate_status != "clean":
        return False
    if anomaly_count > 0:
        return False
    return overall >= min_confidence
