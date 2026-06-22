from __future__ import annotations

from app.modules.finance_os.analytics.repositories.kpi_snapshot_repository import kpi_snapshot_repository


def compare(org_id: str, *, kpi_code: str) -> dict:
    history = kpi_snapshot_repository.history(org_id, kpi_code=kpi_code, limit=13)
    if not history:
        return {"kpi_code": kpi_code, "benchmarks": []}
    current = float(history[0].get("kpi_value") or 0)
    benchmarks = [{"period": "current", "value": current, "snapshot_date": history[0].get("snapshot_date")}]
    if len(history) > 1:
        benchmarks.append({"period": "prior_month", "value": float(history[1].get("kpi_value") or 0), "snapshot_date": history[1].get("snapshot_date")})
    if len(history) > 3:
        benchmarks.append({"period": "prior_quarter", "value": float(history[3].get("kpi_value") or 0), "snapshot_date": history[3].get("snapshot_date")})
    if len(history) > 12:
        benchmarks.append({"period": "prior_year", "value": float(history[12].get("kpi_value") or 0), "snapshot_date": history[12].get("snapshot_date")})
    return {"kpi_code": kpi_code, "benchmarks": benchmarks}
