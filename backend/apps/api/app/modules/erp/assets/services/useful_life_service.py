from __future__ import annotations

from app.modules.erp.assets.ai.useful_life_recommender import recommend_useful_life


def suggest_from_category(category: dict | None) -> dict:
    if not category:
        return {"useful_life_months": 36, "salvage_percent": 5}
    return {
        "useful_life_months": int(category.get("default_useful_life_months") or 36),
        "salvage_percent": float(category.get("default_salvage_percent") or 0),
        "depreciation_method": str(category.get("depreciation_method") or "straight_line"),
    }


def suggest_salvage(*, cost: float, salvage_percent: float) -> float:
    return round(cost * salvage_percent / 100, 2) if cost > 0 else 0.0
