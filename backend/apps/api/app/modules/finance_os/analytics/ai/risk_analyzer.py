from __future__ import annotations

from app.modules.finance_os.analytics.repositories.anomaly_flag_repository import anomaly_flag_repository


def synthesize(org_id: str) -> dict:
    flags = anomaly_flag_repository.list_recent(org_id, limit=20)
    high = [f for f in flags if f.get("severity") == "high"]
    medium = [f for f in flags if f.get("severity") == "medium"]
    return {
        "risk_level": "high" if high else ("medium" if medium else "low"),
        "high_risks": high,
        "medium_risks": medium,
        "summary": f"{len(high)} high and {len(medium)} medium financial risks detected.",
    }
