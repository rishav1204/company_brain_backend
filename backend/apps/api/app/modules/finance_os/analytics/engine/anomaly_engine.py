from __future__ import annotations

from app.modules.finance_os.analytics.engine import trend_engine


def detect(kpis: list[dict], *, prior_kpis: list[dict] | None = None) -> list[dict]:
    """Rule-based anomaly detection on KPI rows."""
    flags: list[dict] = []
    by_code = {k["kpi_code"]: k for k in kpis}
    prior_by_code = {k["kpi_code"]: k for k in (prior_kpis or [])}

    runway = float(by_code.get("treasury.cash_runway_days", {}).get("kpi_value") or 999)
    if runway < 30:
        flags.append({"anomaly_type": "cash_burn", "severity": "high", "payload": {"cash_runway_days": runway}})

    overdue_meta = (by_code.get("compliance.filing_pct") or {}).get("metadata") or {}
    if int(overdue_meta.get("overdue") or 0) > 0:
        flags.append({"anomaly_type": "compliance_risk", "severity": "medium", "payload": overdue_meta})

    dso = float(by_code.get("collections.dso", {}).get("kpi_value") or 0)
    prior_dso = float(prior_by_code.get("collections.dso", {}).get("kpi_value") or dso)
    if prior_dso and (dso - prior_dso) > 10:
        flags.append({"anomaly_type": "collection_slowdown", "severity": "medium", "payload": {"dso": dso, "prior_dso": prior_dso}})

    npm = by_code.get("finance.net_profit_margin")
    prior_npm = prior_by_code.get("finance.net_profit_margin")
    if npm and prior_npm:
        cur = float(npm.get("kpi_value") or 0)
        pri = float(prior_npm.get("kpi_value") or 0)
        if pri and trend_engine.compute_trend_percent(cur, pri) < -15:
            flags.append({"anomaly_type": "revenue_drop", "severity": "high", "payload": {"margin": cur, "prior_margin": pri}})

    return flags
