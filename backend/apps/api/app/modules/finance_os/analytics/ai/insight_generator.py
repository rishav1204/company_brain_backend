from __future__ import annotations

from app.modules.finance_os.analytics.engine import insight_engine
from app.modules.finance_os.analytics.repositories.kpi_snapshot_repository import kpi_snapshot_repository
from app.services.llm_provider import llm_provider


def generate(org_id: str, *, limit: int = 5) -> list[dict]:
    kpis = kpi_snapshot_repository.list(org_id, limit=50)
    insights = insight_engine.generate_insights(kpis)
    if not llm_provider.is_ready() or not insights:
        return insights[:limit]
    narrated = []
    for ins in insights[:limit]:
        try:
            out = llm_provider.generate_json(
                org_id=org_id,
                system_prompt="Narrate executive insight in one sentence. JSON only.",
                user_prompt=f"Title: {ins['title']}\nDescription: {ins['description']}\nReturn JSON: {{description: str}}",
                estimated_tokens=400,
            )
            ins = {**ins, "description": str(out.get("description") or ins["description"])}
        except Exception:
            pass
        narrated.append(ins)
    return narrated
