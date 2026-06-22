from __future__ import annotations

from app.modules.finance_os.analytics.engine import trend_engine


def generate_insights(kpis: list[dict], *, prior_kpis: list[dict] | None = None) -> list[dict]:
    insights: list[dict] = []
    by_code = {k["kpi_code"]: k for k in kpis}
    prior_by_code = {k["kpi_code"]: k for k in (prior_kpis or [])}

    dso = by_code.get("collections.dso")
    if dso and prior_by_code.get("collections.dso"):
        cur = float(dso["kpi_value"])
        pri = float(prior_by_code["collections.dso"]["kpi_value"])
        pct = trend_engine.compute_trend_percent(cur, pri)
        if abs(pct) >= 5:
            direction = "increased" if pct > 0 else "improved"
            insights.append({
                "insight_type": "collections",
                "title": f"DSO {direction} {abs(pct):.1f}%",
                "description": f"Days sales outstanding moved from {pri:.1f} to {cur:.1f} days.",
                "severity": "warning" if pct > 0 else "info",
                "evidence": {"dso": cur, "prior_dso": pri, "change_pct": pct},
            })

    npm = by_code.get("finance.net_profit_margin")
    if npm and prior_by_code.get("finance.net_profit_margin"):
        cur = float(npm["kpi_value"])
        pri = float(prior_by_code["finance.net_profit_margin"]["kpi_value"])
        pct = trend_engine.compute_trend_percent(cur, pri)
        if abs(pct) >= 5:
            insights.append({
                "insight_type": "profitability",
                "title": f"Net margin changed {pct:+.1f}%",
                "description": f"Net profit margin moved from {pri:.1f}% to {cur:.1f}%.",
                "severity": "warning" if pct < 0 else "info",
                "evidence": {"margin": cur, "prior_margin": pri},
            })

    runway = by_code.get("treasury.cash_runway_days")
    if runway and float(runway["kpi_value"]) < 45:
        insights.append({
            "insight_type": "treasury",
            "title": "Cash runway below 45 days",
            "description": f"Estimated cash runway is {float(runway['kpi_value']):.0f} days based on current burn.",
            "severity": "high",
            "evidence": {"cash_runway_days": float(runway["kpi_value"])},
        })

    close_eff = by_code.get("close.efficiency_score")
    if close_eff and float(close_eff["kpi_value"]) < 60:
        insights.append({
            "insight_type": "close",
            "title": "Period close efficiency needs attention",
            "description": f"Close workflow efficiency score is {float(close_eff['kpi_value']):.0f}/100.",
            "severity": "medium",
            "evidence": {"efficiency_score": float(close_eff["kpi_value"])},
        })

    acc = by_code.get("forecast.accuracy_avg")
    if acc and float(acc["kpi_value"]) > 20:
        insights.append({
            "insight_type": "forecast",
            "title": "Forecast accuracy drift detected",
            "description": f"Average forecast variance is {float(acc['kpi_value']):.1f}%.",
            "severity": "medium",
            "evidence": {"accuracy_avg": float(acc["kpi_value"])},
        })

    return insights
