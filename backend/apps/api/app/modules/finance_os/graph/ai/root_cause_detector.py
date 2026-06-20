from __future__ import annotations

from app.modules.finance_os.graph.engine.causality_engine import explain_chain


def detect_root_cause(org_id: str, entity_id: str) -> dict:
    chain = explain_chain(org_id, entity_id)
    explanation = chain.get("explanation") or []
    path_count = len(explanation) if isinstance(explanation, list) else (1 if explanation else 0)
    detected = path_count >= 2 or chain.get("confidence", 0) >= 0.8
    result = {"entity_id": entity_id, "detected": detected, **chain}
    if detected:
        try:
            from app.modules.finance_os.graph.bridges.memory_bridge import write_causal_summary

            write_causal_summary(org_id, entity_id, chain)
        except Exception:
            pass
    return result
