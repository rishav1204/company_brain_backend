from __future__ import annotations


class ConfidenceEngine:
    def score_fields(self, data: dict) -> dict:
        out: dict[str, dict] = {}
        for key, value in data.items():
            if isinstance(value, (int, float)):
                score = 0.95
            elif isinstance(value, str) and value.strip():
                score = 0.9
            elif isinstance(value, list) and value:
                score = 0.85
            elif isinstance(value, dict) and value:
                score = 0.88
            else:
                score = 0.35
            out[key] = {"value": value, "confidence": score}
        return out

    def aggregate(self, field_scores: dict) -> float:
        if not field_scores:
            return 0.0
        scores = [float(v.get("confidence", 0)) for v in field_scores.values()]
        return round(sum(scores) / max(1, len(scores)), 4)


confidence_engine = ConfidenceEngine()
