from __future__ import annotations

from app.modules.finance_os.agents.bridges import m12_bridge, m21_bridge, m23_bridge, m25_bridge, m26_bridge, m27_bridge, m28_bridge
from app.modules.finance_os.agents.ai.policy_reasoner import check as check_policy
from app.modules.finance_os.agents.schemas.agents_schema import AgentContext
from app.modules.finance_os.agents.orchestrator.task_router import resolve_agent, task_type_for


def build(org_id: str, agent_type: str, payload: dict | None = None) -> AgentContext:
    payload = payload or {}
    agent_name = resolve_agent(agent_type, payload)
    entity_type = str(payload.get("entity_type") or payload.get("object_type") or "")
    entity_id = str(payload.get("entity_id") or payload.get("object_id") or payload.get("invoice_id") or "")

    memory_snippets = m27_bridge.search(org_id, query=f"{agent_name} {entity_id}", entity_type=entity_type or None, entity_id=entity_id or None)
    graph_paths = m28_bridge.lineage(org_id, entity_id) if entity_id else []
    erp_facts = {
        "invoice": m25_bridge.invoice_context(org_id, entity_id) if entity_id else {},
        "workflow": m26_bridge.workflow_context(org_id, payload.get("workflow_id")),
        "reconciliation": m23_bridge.match_context(org_id, payload.get("bank_account_id")),
        "gst": m21_bridge.compliance_context(org_id, entity_id),
        "fiscal": m12_bridge.period_context(org_id, payload.get("period_id")),
    }
    policy_flags = check_policy(payload)
    completeness = sum(1 for v in [entity_type, entity_id] if v) / 2.0
    erp_score = sum(1 for v in erp_facts.values() if v) / max(1, len(erp_facts))
    data_quality_score = round(0.6 * completeness + 0.4 * erp_score, 2)

    return AgentContext(
        org_id=org_id,
        agent_name=agent_name,
        task_type=task_type_for(agent_name, payload),
        entity_type=entity_type or None,
        entity_id=entity_id or None,
        memory_snippets=memory_snippets,
        graph_paths=graph_paths if isinstance(graph_paths, list) else [graph_paths] if graph_paths else [],
        erp_facts=erp_facts,
        policy_flags=policy_flags,
        data_quality_score=data_quality_score,
        raw_payload=payload,
    )
