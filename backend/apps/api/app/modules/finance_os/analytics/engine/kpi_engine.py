from __future__ import annotations

from datetime import date

from app.modules.finance_os.analytics.read_models import (
    compliance_read_models,
    finance_read_models,
    forecast_read_models,
    reconciliation_read_models,
    treasury_read_models,
    workflow_read_models,
)


def compute_all(org_id: str, *, fiscal_period_id: str | None = None, snapshot_date: str | None = None) -> list[dict]:
    snap = (snapshot_date or date.today().isoformat())[:10]
    finance = finance_read_models.load_finance(org_id, fiscal_period_id=fiscal_period_id)
    treasury = treasury_read_models.load_treasury(org_id)
    compliance = compliance_read_models.load_compliance(org_id)
    recon = reconciliation_read_models.load_reconciliation(org_id)
    close = workflow_read_models.load_close(org_id, fiscal_period_id=fiscal_period_id or finance.get("fiscal_period_id"))
    forecast_acc = forecast_read_models.load_forecast_accuracy(org_id)
    forecast_cash = forecast_read_models.load_forecast(org_id, forecast_type="cash", horizon_days=30)

    kpis: list[dict] = []
    if finance.get("ready"):
        fp = str(finance.get("fiscal_period_id"))
        days = finance_read_models.days_in_period(org_id, fiscal_period_id=fp)
        revenue = float(finance.get("revenue") or 0)
        gross = float(finance.get("gross_profit") or 0)
        net = float(finance.get("net_profit") or 0)
        expense = float(finance.get("expense") or 0)
        ar = float(finance.get("ar_outstanding") or 0)
        ap = float(finance.get("ap_outstanding") or 0)

        if revenue:
            kpis.append({"kpi_code": "finance.gross_profit_margin", "kpi_value": round(gross / revenue * 100, 2), "metadata": {"revenue": revenue}})
            kpis.append({"kpi_code": "finance.net_profit_margin", "kpi_value": round(net / revenue * 100, 2), "metadata": {"revenue": revenue}})
            kpis.append({"kpi_code": "finance.ebitda_margin", "kpi_value": round(gross / revenue * 100, 2), "metadata": {"proxy": True}})
            kpis.append({"kpi_code": "collections.dso", "kpi_value": round((ar / revenue) * days, 2), "metadata": {"ar": ar, "days": days}})
        if expense:
            kpis.append({"kpi_code": "vendor.dpo", "kpi_value": round((ap / expense) * days, 2), "metadata": {"ap": ap, "days": days}})
        kpis.append({"kpi_code": "working_capital.net", "kpi_value": round(ar - ap, 2), "metadata": {"ar": ar, "ap": ap}})

    available = float(treasury.get("available_cash") or 0)
    daily_burn = max(float(forecast_cash.get("avg_daily_forecast") or 0), 1.0)
    if expense := float(finance.get("expense") or 0) if finance.get("ready") else 0:
        daily_burn = max(daily_burn, expense / 30.0)
    kpis.append({"kpi_code": "treasury.cash_runway_days", "kpi_value": round(available / daily_burn, 1), "metadata": {"available_cash": available}})
    if treasury.get("liquidity_coverage") is not None:
        kpis.append({"kpi_code": "treasury.liquidity_coverage", "kpi_value": float(treasury["liquidity_coverage"]), "metadata": {"health_band": treasury.get("health_band")}})

    kpis.append({"kpi_code": "compliance.filing_pct", "kpi_value": float(compliance.get("filing_compliance_pct") or 0), "metadata": {"overdue": compliance.get("overdue_count")}})
    kpis.append({"kpi_code": "compliance.penalty_exposure", "kpi_value": float(compliance.get("penalty_exposure") or 0), "metadata": {}})
    kpis.append({"kpi_code": "reconciliation.rate", "kpi_value": float(recon.get("reconciliation_rate") or 0), "metadata": recon})

    if close.get("close_duration_days") is not None:
        kpis.append({"kpi_code": "close.duration_days", "kpi_value": float(close["close_duration_days"]), "metadata": {"period": close.get("fiscal_period_id")}})
    kpis.append({"kpi_code": "close.efficiency_score", "kpi_value": float(close.get("efficiency_score") or 0), "metadata": {}})
    kpis.append({"kpi_code": "close.sla_breach_count", "kpi_value": float(close.get("sla_breach_count") or 0), "metadata": {}})

    if forecast_acc.get("accuracy_avg") is not None:
        kpis.append({"kpi_code": "forecast.accuracy_avg", "kpi_value": float(forecast_acc["accuracy_avg"]), "metadata": {"count": len(forecast_acc.get("rows") or [])}})

    for row in kpis:
        row["snapshot_date"] = snap
    return kpis
