from __future__ import annotations

import math
from datetime import datetime, timezone


def recency_decay(created_at: str | None, *, half_life_days: float = 90.0) -> float:
    if not created_at:
        return 0.5
    try:
        ts = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        age_days = max((datetime.now(timezone.utc) - ts).total_seconds() / 86400, 0.0)
    except Exception:
        return 0.5
    return math.exp(-0.693 * age_days / half_life_days)


def keyword_match(query: str, content: str) -> float:
    terms = {t for t in query.lower().split() if t}
    if not terms:
        return 0.0
    lowered = content.lower()
    hits = sum(1 for t in terms if t in lowered)
    return hits / len(terms)


def frequency_boost(entity_memory_count: int) -> float:
    if entity_memory_count >= 20:
        return 1.0
    if entity_memory_count >= 10:
        return 0.7
    if entity_memory_count >= 3:
        return 0.4
    return 0.1


def rank_candidates(candidates: list[dict], *, query: str) -> list[dict]:
    ranked: list[dict] = []
    for item in candidates:
        if item.get("status") in {"expired", "archived"}:
            continue
        vector_sim = 1.0 - float(item.get("distance", item.get("vector_distance", 0.5)))
        vector_sim = max(0.0, min(vector_sim, 1.0))
        importance = float(item.get("importance_score", 50)) / 100.0
        recency = recency_decay(item.get("created_at"))
        freq = frequency_boost(int(item.get("entity_memory_count", 1)))
        kw = keyword_match(query, str(item.get("content", "")))
        final_score = (
            0.35 * vector_sim
            + 0.25 * importance
            + 0.20 * recency
            + 0.10 * freq
            + 0.10 * kw
        )
        ranked.append({**item, "final_score": round(final_score, 4)})
    ranked.sort(key=lambda x: x["final_score"], reverse=True)
    return ranked
