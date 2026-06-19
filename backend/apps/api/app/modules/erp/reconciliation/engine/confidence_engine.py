from __future__ import annotations

DEFAULT_WEIGHTS = {
    "amount_exact": 40.0,
    "amount_near": 30.0,
    "date_exact": 20.0,
    "date_close": 12.0,
    "date_week": 5.0,
    "reference_match": 30.0,
    "narration_fuzzy": 10.0,
    "counterparty_match": 10.0,
    "source_id_match": 100.0,
}


def load_weights(rules: list[dict] | None) -> dict[str, float]:
    if not rules:
        return dict(DEFAULT_WEIGHTS)
    weights = dict(DEFAULT_WEIGHTS)
    type_map = {
        "amount": "amount_exact",
        "date": "date_exact",
        "reference": "reference_match",
        "narration": "narration_fuzzy",
        "counterparty": "counterparty_match",
    }
    for rule in rules:
        if not rule.get("is_active", True):
            continue
        rt = str(rule.get("rule_type") or "")
        key = type_map.get(rt, rt)
        weights[key] = float(rule.get("weight") or weights.get(key, 0))
    return weights


def score_to_band(score_100: float) -> str:
    if score_100 >= 95:
        return "auto_suggest"
    if score_100 >= 80:
        return "likely_match"
    if score_100 >= 60:
        return "review"
    return "manual"


def compute_confidence(factors: dict[str, bool], weights: dict[str, float] | None = None) -> dict:
    w = weights or DEFAULT_WEIGHTS
    if factors.get("source_id_match"):
        return {"confidence_score": 1.0, "confidence_100": 100.0, "band": "auto_suggest", "factors": ["source_id_match"]}
    total = 0.0
    applied: list[str] = []
    for key, hit in factors.items():
        if hit and key in w:
            total += w[key]
            applied.append(key)
    confidence_100 = min(100.0, round(total, 2))
    return {
        "confidence_score": round(confidence_100 / 100.0, 4),
        "confidence_100": confidence_100,
        "band": score_to_band(confidence_100),
        "factors": applied,
    }
