from __future__ import annotations

from app.modules.erp.assets.ai.asset_classifier import classify_asset
from app.modules.erp.assets.ai.useful_life_recommender import recommend_useful_life


def suggest(description: str, amount: float) -> dict:
    hints = classify_asset(description)
    return {
        "description": description,
        "amount": amount,
        "category": hints,
        "useful_life_months": recommend_useful_life(hints),
        "should_capitalize": amount >= 50000,
    }
