from __future__ import annotations


def predict_notice_risk(*, risk_flags: list[dict]) -> dict:
    high = [f for f in risk_flags if f.get("severity") == "high"]
    return {
        "notice_risk": "elevated" if len(high) >= 2 else "moderate" if high else "low",
        "factors": [f.get("type") for f in high],
        "stub": True,
    }
