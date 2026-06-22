from __future__ import annotations

from app.services.llm_provider import llm_provider


def explain(*, kpi_code: str, trend_direction: str, trend_percent: float) -> str:
    base = f"{kpi_code} trend is {trend_direction} ({trend_percent:+.1f}% MoM)."
    if not llm_provider.is_ready():
        return base
    try:
        out = llm_provider.generate_text(
            org_id="",
            system_prompt="Explain KPI trend for executives in one sentence.",
            user_prompt=base,
            estimated_tokens=200,
        )
        return str(out or base)
    except Exception:
        return base
