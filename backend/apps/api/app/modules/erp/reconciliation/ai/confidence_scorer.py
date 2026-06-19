from __future__ import annotations


def score_breakdown(match_result: dict) -> dict:
    return {
        "confidence_score": match_result.get("confidence_score", 0),
        "confidence_100": match_result.get("confidence_100", match_result.get("confidence_score", 0) * 100),
        "band": match_result.get("band", "manual"),
        "factors": match_result.get("factors") or [],
        "recommendation": _recommendation(match_result),
    }


def _recommendation(match_result: dict) -> str:
    band = match_result.get("band", "manual")
    if band == "auto_suggest":
        return "High confidence — review and approve"
    if band == "likely_match":
        return "Likely match — finance review recommended"
    if band == "review":
        return "Moderate confidence — manual review required"
    return "Low confidence — manual matching required"
