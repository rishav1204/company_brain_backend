from __future__ import annotations

from app.modules.finance_os.graph.engine.lineage_engine import format_lineage_paths
from app.modules.finance_os.graph.engine.causality_engine import explain_chain


def graph_trace_for_subject(org_id: str, subject_ref: str | None) -> list[str]:
    if not subject_ref:
        return []
    try:
        from app.modules.finance_os.graph.engine.lineage_engine import get_lifecycle

        lifecycle = get_lifecycle(org_id, subject_ref, max_depth=4)
        paths = lifecycle.get("paths") or []
        if paths:
            return paths
        chain = explain_chain(org_id, subject_ref)
        exp = chain.get("explanation")
        if isinstance(exp, list):
            return exp
        return [str(exp)] if exp else []
    except Exception:
        return []
