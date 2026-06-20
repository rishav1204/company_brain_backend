from __future__ import annotations

IMPORTANCE_THRESHOLD = 50

BAND_THRESHOLDS = (
    (90, "critical"),
    (70, "high"),
    (50, "medium"),
    (0, "low"),
)

TTL_BY_BAND = {
    "critical": "forever",
    "high": "180d",
    "medium": "90d",
    "low": "30d",
}

EVENT_WEIGHTS: dict[str, float] = {
    "payment.executed": 65,
    "erp.payment.completed": 65,
    "approval.completed": 60,
    "approval.rejected": 72,
    "workflow.approved": 60,
    "workflow.intelligence.completed": 75,
    "invoice.predicted": 55,
    "invoice.duplicate_detected": 70,
    "invoice.anomaly_detected": 78,
    "reconciliation.completed": 58,
    "reconciliation.adjustment.posted": 68,
    "liquidity_alert.created": 80,
    "cash.forecast.updated": 55,
    "treasury.risk.detected": 82,
    "compliance.alert.generated": 85,
    "gst.mismatch.detected": 80,
    "decision.recorded": 70,
    "journal.posted": 62,
    "erp.invoice.approved": 58,
    "memory.write": 55,
}


def importance_band(score: float) -> str:
    for threshold, band in BAND_THRESHOLDS:
        if score >= threshold:
            return band
    return "low"


def default_ttl_for_band(band: str) -> str:
    return TTL_BY_BAND.get(band, "90d")


def financial_impact_weight(amount: float | None) -> float:
    if amount is None or amount <= 0:
        return 0.0
    if amount >= 5_000_000:
        return 20.0
    if amount >= 500_000:
        return 12.0
    if amount >= 50_000:
        return 6.0
    return 2.0


def recurrence_boost(prior_count: int) -> float:
    if prior_count >= 10:
        return 15.0
    if prior_count >= 5:
        return 10.0
    if prior_count >= 2:
        return 5.0
    return 0.0


def risk_boost(*, anomaly: bool = False, duplicate: bool = False, compliance: bool = False) -> float:
    boost = 0.0
    if anomaly:
        boost += 12.0
    if duplicate:
        boost += 8.0
    if compliance:
        boost += 15.0
    return boost


def human_action_boost(*, override: bool = False, rejection: bool = False) -> float:
    if rejection:
        return 10.0
    if override:
        return 8.0
    return 0.0


def compute_importance(
    *,
    event_type: str,
    amount: float | None = None,
    prior_count: int = 0,
    anomaly: bool = False,
    duplicate: bool = False,
    compliance: bool = False,
    override: bool = False,
    rejection: bool = False,
    base_score: float | None = None,
) -> float:
    base = base_score if base_score is not None else EVENT_WEIGHTS.get(event_type, 45.0)
    score = (
        base
        + financial_impact_weight(amount)
        + recurrence_boost(prior_count)
        + risk_boost(anomaly=anomaly, duplicate=duplicate, compliance=compliance)
        + human_action_boost(override=override, rejection=rejection)
    )
    return min(max(score, 0.0), 100.0)


def passes_importance_gate(score: float, *, force: bool = False, threshold: float = IMPORTANCE_THRESHOLD) -> bool:
    return force or score >= threshold
