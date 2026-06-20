from __future__ import annotations

from app.modules.finance_os.agents.agents.ap_agent import ApAgent
from app.modules.finance_os.agents.agents.base_agent import BaseAgent
from app.modules.finance_os.agents.agents.close_agent import CloseAgent
from app.modules.finance_os.agents.agents.collections_agent import CollectionsAgent
from app.modules.finance_os.agents.agents.gst_agent import GstAgent
from app.modules.finance_os.agents.agents.reconciliation_agent import ReconciliationAgent
from app.modules.finance_os.agents.agents.treasury_agent import TreasuryAgent

AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    "ap_agent": ApAgent,
    "reconciliation_agent": ReconciliationAgent,
    "gst_agent": GstAgent,
    "close_agent": CloseAgent,
    "collections_agent": CollectionsAgent,
    "treasury_agent": TreasuryAgent,
}

AGENT_CATALOG = [
    {
        "agent_name": "ap_agent",
        "aliases": ["ap_exception_agent", "ap_exception"],
        "capabilities": ["invoice_review", "duplicate_detection", "workflow_launch"],
        "trigger_events": ["invoice.anomaly_detected", "invoice.duplicate_detected"],
    },
    {
        "agent_name": "reconciliation_agent",
        "aliases": [],
        "capabilities": ["match_suggestion", "exception_explain"],
        "trigger_events": ["reconciliation.exception.created", "bank.statement.imported"],
    },
    {
        "agent_name": "gst_agent",
        "aliases": [],
        "capabilities": ["filing_prep", "risk_flags"],
        "trigger_events": ["gst.mismatch.detected", "erp.gst.return.generated"],
    },
    {
        "agent_name": "close_agent",
        "aliases": ["close_orchestration_agent"],
        "capabilities": ["close_checklist", "workflow_launch"],
        "trigger_events": ["erp.period.close.requested"],
    },
    {
        "agent_name": "collections_agent",
        "aliases": [],
        "capabilities": ["overdue_ranking", "follow_up"],
        "trigger_events": ["invoice.due"],
    },
    {
        "agent_name": "treasury_agent",
        "aliases": ["cashflow_risk_agent"],
        "capabilities": ["liquidity_advisory"],
        "trigger_events": ["liquidity_alert.created", "treasury.risk.detected"],
    },
]


def get_agent(agent_name: str) -> BaseAgent:
    cls = AGENT_REGISTRY.get(agent_name)
    if not cls:
        raise ValueError(f"Unknown agent: {agent_name}")
    return cls()
