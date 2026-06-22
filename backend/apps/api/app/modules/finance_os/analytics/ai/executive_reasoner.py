from __future__ import annotations

from app.modules.finance_os.analytics.repositories.insight_repository import insight_repository
from app.modules.finance_os.analytics.repositories.kpi_snapshot_repository import kpi_snapshot_repository
from app.modules.finance_os.analytics.services.executive_dashboard_service import executive_dashboard_service


def build_context(org_id: str, question: str) -> str:
    parts: list[str] = [f"Question: {question}"]
    try:
        dash = executive_dashboard_service.get(org_id)
        parts.append(f"Dashboard snapshot: {dash.get('snapshot_date')}")
        widgets = dash.get("widgets") or {}
        for k, v in widgets.items():
            if v:
                parts.append(f"{k}: {v.get('kpi_value') if isinstance(v, dict) else v}")
    except Exception:
        pass
    try:
        kpis = kpi_snapshot_repository.list(org_id, limit=15)
        for k in kpis[:10]:
            parts.append(f"KPI {k.get('kpi_code')}: {k.get('kpi_value')}")
    except Exception:
        pass
    try:
        for ins in insight_repository.list(org_id, limit=5):
            parts.append(f"Insight [{ins.get('severity')}]: {ins.get('title')} — {ins.get('description')}")
    except Exception:
        pass
    try:
        from app.modules.finance_os.memory.ai.memory_reasoner import build_context as mem_ctx

        mem = mem_ctx(org_id, question)
        if mem:
            parts.append(f"Memory context: {mem[:600]}")
    except Exception:
        pass
    return "\n".join(parts)
