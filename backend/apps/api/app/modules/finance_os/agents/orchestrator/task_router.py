from __future__ import annotations

EVENT_AGENT_MAP: dict[str, str] = {
    "invoice.anomaly_detected": "ap_agent",
    "invoice.duplicate_detected": "ap_agent",
    "invoice.predicted": "ap_agent",
    "reconciliation.completed": "reconciliation_agent",
    "reconciliation.exception.created": "reconciliation_agent",
    "bank.statement.imported": "reconciliation_agent",
    "gst.mismatch.detected": "gst_agent",
    "erp.gst.return.generated": "gst_agent",
    "compliance.due": "gst_agent",
    "erp.period.close.requested": "close_agent",
    "scheduler.compliance.daily": "close_agent",
    "invoice.due": "collections_agent",
    "liquidity_alert.created": "treasury_agent",
    "treasury.risk.detected": "treasury_agent",
}


def resolve_agent(agent_type: str | None, payload: dict | None = None) -> str:
    if agent_type:
        key = agent_type.strip().lower()
        aliases = {
            "ap_exception": "ap_agent",
            "ap_exception_agent": "ap_agent",
            "close_orchestration": "close_agent",
            "close_orchestration_agent": "close_agent",
            "cashflow_risk": "treasury_agent",
            "cashflow_risk_agent": "treasury_agent",
        }
        return aliases.get(key, key)
    payload = payload or {}
    event_type = str(payload.get("source_event_type") or payload.get("event_type") or "")
    return EVENT_AGENT_MAP.get(event_type, "ap_agent")


def task_type_for(agent_name: str, payload: dict | None = None) -> str:
    payload = payload or {}
    if payload.get("task_type"):
        return str(payload["task_type"])
    defaults = {
        "ap_agent": "invoice_review",
        "reconciliation_agent": "bank_match",
        "gst_agent": "gst_review",
        "close_agent": "period_close",
        "collections_agent": "collection_followup",
        "treasury_agent": "liquidity_advisory",
    }
    return defaults.get(agent_name, "general")
