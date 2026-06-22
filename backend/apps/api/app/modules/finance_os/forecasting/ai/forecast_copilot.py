from __future__ import annotations

from app.modules.finance_os.forecasting.ai.forecast_reasoner import build_context
from app.services.llm_provider import llm_provider


def explain(*, org_id: str, forecast_type: str, horizon_days: int, rows: list[dict], evidence: dict | None = None) -> dict:
    context = build_context(forecast_type=forecast_type, horizon_days=horizon_days, forecast_rows=rows, evidence=evidence)
    if not llm_provider.is_ready():
        return {"answer": fallback_explanation(forecast_type=forecast_type, rows=rows, evidence=evidence), "sources": evidence or {}}
    try:
        out = llm_provider.generate_json(
            org_id=org_id,
            system_prompt="You are a CFO-grade forecasting explainer. Output strict JSON only.",
            user_prompt=(
                "Explain this forecast in plain language. Include: top drivers, top risks, and what changed.\n\n"
                f"{context}\n\nReturn JSON: {{answer: str, drivers: [str], risks: [str]}}"
            ),
            estimated_tokens=1400,
        )
        return {
            "answer": str(out.get("answer") or ""),
            "sources": {**(evidence or {}), "drivers": out.get("drivers") or [], "risks": out.get("risks") or []},
        }
    except Exception:
        return {"answer": fallback_explanation(forecast_type=forecast_type, rows=rows, evidence=evidence), "sources": evidence or {}}


def fallback_explanation(*, forecast_type: str, rows: list[dict], evidence: dict | None = None) -> str:
    evidence = evidence or {}
    if not rows:
        return f"No forecast rows available for {forecast_type}."
    first = rows[0].get("forecast_value")
    last = rows[-1].get("forecast_value")
    drivers = ", ".join(str(x) for x in (evidence.get("drivers") or [])[:3])
    risks = ", ".join(str(x) for x in (evidence.get("risks") or [])[:3])
    base = f"{forecast_type} forecast from {rows[0].get('forecast_date')} to {rows[-1].get('forecast_date')}: {first} → {last}."
    if drivers:
        base += f" Drivers: {drivers}."
    if risks:
        base += f" Risks: {risks}."
    return base

