from __future__ import annotations

from app.modules.finance_os.forecasting.ai.forecast_copilot import explain as copilot_explain


def build_evidence(*, inputs: dict, memory_count: int = 0, graph_count: int = 0) -> dict:
    drivers = []
    if inputs.get("starting_cash") is not None:
        drivers.append("starting_cash")
    if inputs.get("ar_outstanding_total") is not None:
        drivers.append("ar_outstanding_total")
    if inputs.get("ap_outstanding_total") is not None:
        drivers.append("ap_outstanding_total")
    risks = []
    if float(inputs.get("min_cash", 0) or 0) < 0:
        risks.append("cash_negative_risk")
    if memory_count == 0:
        risks.append("no_memory_adjustments")
    if graph_count == 0:
        risks.append("no_graph_evidence")
    return {"drivers": drivers, "risks": risks, "inputs": inputs}


def explain_forecast(
    org_id: str,
    *,
    forecast_type: str,
    horizon_days: int,
    rows: list[dict],
    inputs: dict,
    memory_count: int = 0,
    graph_count: int = 0,
) -> dict:
    evidence = build_evidence(inputs=inputs, memory_count=memory_count, graph_count=graph_count)
    return copilot_explain(org_id=org_id, forecast_type=forecast_type, horizon_days=horizon_days, rows=rows, evidence=evidence)

