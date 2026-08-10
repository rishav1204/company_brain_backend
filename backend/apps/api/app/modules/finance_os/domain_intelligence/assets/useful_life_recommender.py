from __future__ import annotations

DEFAULT_MONTHS = {
    "COMPUTERS": 36,
    "FURNITURE": 60,
    "VEHICLES": 60,
    "BUILDINGS": 240,
    "MACHINERY": 120,
    "SOFTWARE": 36,
}


def recommend_useful_life(hints: dict | None) -> int:
    if not hints:
        return 36
    code = str(hints.get("category_code") or "").upper()
    if hints.get("useful_life_months"):
        return int(hints["useful_life_months"])
    return DEFAULT_MONTHS.get(code, 36)
