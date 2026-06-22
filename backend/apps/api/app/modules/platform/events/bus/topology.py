from __future__ import annotations

from app.core.config import settings


def platform_queue_groups() -> dict[str, str]:
    return {
        "ingestion.sync": settings.queue_ingestion_sync,
        "ingestion.retry": settings.queue_ingestion_retry,
        "processing.chunk": settings.queue_processing_chunk,
        "processing.embed": settings.queue_processing_embed,
        "processing.extract": settings.queue_processing_extract,
        "graph.upsert": settings.queue_graph_upsert,
        "memory.write": settings.queue_memory_write,
        "retrieval.precompute": settings.queue_retrieval_precompute,
        "agent.run": settings.queue_agent_run,
        "agent.action": settings.queue_agent_action,
        "notifications.dispatch": settings.queue_notifications_dispatch,
        "notifications.email": settings.queue_notifications_email,
        "notifications.whatsapp": settings.queue_notifications_whatsapp,
        "notifications.push": settings.queue_notifications_push,
        "audit.persist": settings.queue_audit_persist,
        "workflow.execution": settings.queue_workflow_execution,
        "workflow.approvals": settings.queue_workflow_approvals,
        "workflow.escalations": settings.queue_workflow_escalations,
        "workflow.sla": settings.queue_workflow_sla,
        "workflow.retries": settings.queue_workflow_retries,
        "ai.ocr": settings.queue_ai_ocr,
        "ai.reconciliation": settings.queue_ai_reconciliation,
        "ai.risk": settings.queue_ai_risk,
        "ai.memory": settings.queue_ai_memory,
        "ai.forecasting": settings.queue_ai_forecasting,
        "integration.gst": settings.queue_integration_gst,
        "integration.bank": settings.queue_integration_bank,
        "integration.webhooks": settings.queue_integration_webhooks,
        "integration.email": settings.queue_integration_email,
        "reports.generate": settings.queue_reports_generate,
        "reports.refresh": settings.queue_reports_refresh,
    }


def route_platform_event(event_type: str) -> str:
    groups = platform_queue_groups()
    if event_type.startswith("erp.") or event_type in {"invoice.created", "payment.completed", "journal.posted"}:
        return groups["workflow.execution"]
    if event_type.startswith("workflow.advance") or event_type.startswith("approval."):
        return groups["workflow.approvals"]
    if event_type.startswith("workflow.retry"):
        return groups["workflow.retries"]
    if event_type.startswith("sla.") or event_type.startswith("workflow.sla"):
        return groups["workflow.sla"]
    if event_type.startswith("workflow.escalated") or event_type == "workflow.escalated":
        return groups["workflow.escalations"]
    if event_type.startswith("workflow."):
        return groups["workflow.execution"]
    if event_type.startswith("invoice.ai") or event_type.startswith("reconciliation.match"):
        return groups["ai.reconciliation"]
    if event_type.startswith("payment.risk") or event_type.startswith("risk."):
        return groups["ai.risk"]
    if event_type.startswith("ai.ocr") or event_type.endswith(".ocr"):
        return groups["ai.ocr"]
    if event_type.startswith("ai.memory") or event_type.startswith("memory."):
        return groups["ai.memory"]
    if event_type.startswith("forecast.") or event_type.startswith("ai.forecast"):
        return groups["ai.forecasting"]
    if event_type.startswith("agent.run"):
        return groups["agent.run"]
    if event_type.startswith("agent.action"):
        return groups["agent.action"]
    if event_type.startswith("bank.") or event_type.startswith("integration.bank"):
        return groups["integration.bank"]
    if event_type.startswith("gst.") or event_type.startswith("integration.gst"):
        return groups["integration.gst"]
    if event_type.startswith("webhook."):
        return groups["integration.webhooks"]
    if event_type.startswith("notifications.email"):
        return groups["notifications.email"]
    if event_type.startswith("notifications.whatsapp"):
        return groups["notifications.whatsapp"]
    if event_type.startswith("notifications.push"):
        return groups["notifications.push"]
    if event_type.startswith("notifications."):
        return groups["notifications.dispatch"]
    if event_type.startswith("reports.generate"):
        return groups["reports.generate"]
    if event_type.startswith("reports."):
        return groups["reports.refresh"]
    if event_type.startswith("source.sync"):
        return groups["ingestion.sync"]
    if event_type.startswith("document.") or event_type.startswith("chunk."):
        return groups["processing.embed"]
    if event_type.startswith("entity."):
        return groups["processing.extract"]
    if event_type.startswith("graph."):
        return groups["graph.upsert"]
    if event_type.startswith("decision."):
        return groups["memory.write"]
    if event_type.startswith("scheduler."):
        return groups["workflow.sla"]
    return groups["audit.persist"]
