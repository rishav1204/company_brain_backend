"""Routes queue envelopes to domain-specific event consumer handlers."""
from __future__ import annotations

from app.modules.platform.events.consumers import erp_consumer, finance_os_consumer, ingestion_consumer, workflow_consumer
from app.services.event_consumers_handlers import (
    _consume_audit_event,
    _consume_document_intelligence_event,
    _consume_document_security_event,
    _consume_governance_event,
    _consume_integration_event,
    _consume_notification_event,
    _consume_reports_event,
    _consume_scheduler_event,
    _push_document_realtime,
    _should_route_domain_notification,
)
from app.services.event_org_validation import require_org_id
from app.services.logger import log_event


def consume_event(queue: str, envelope: dict) -> None:
    require_org_id(str(envelope.get("org_id", "")), context="event_consume")
    if queue.endswith("ingestion.sync"):
        ingestion_consumer.consume_ingestion_event(envelope)
    elif queue.endswith("ingestion.retry"):
        ingestion_consumer.consume_retry_event(envelope)
    elif queue.endswith("processing.chunk"):
        ingestion_consumer.consume_chunk_processing_event(envelope)
    elif queue.endswith("processing.embed"):
        ingestion_consumer.consume_chunk_processing_event(envelope)
    elif queue.endswith("processing.extract"):
        ingestion_consumer.consume_extract_event(envelope)
    elif queue.endswith("graph.upsert"):
        ingestion_consumer.consume_graph_event(envelope)
    elif queue.endswith("memory.write"):
        finance_os_consumer.consume_memory_event(envelope)
    elif queue.endswith("retrieval.precompute"):
        finance_os_consumer.consume_memory_event(envelope)
    elif queue.endswith("agent.run"):
        finance_os_consumer.consume_agent_run_event(envelope)
    elif queue.endswith("agent.action"):
        finance_os_consumer.consume_agent_action_event(envelope)
        if str(envelope.get("event_type", "")) == "agent.action.planned":
            finance_os_consumer.consume_agent_plan_event(envelope)
    elif queue.endswith("notifications.dispatch"):
        _consume_notification_event(envelope, queue=queue)
    elif queue.endswith("audit.persist"):
        _consume_audit_event(envelope)
    elif str(envelope.get("event_type", "")) in {
        "audit.log.created",
        "policy.violation.detected",
        "policy.evaluated",
        "policy.approved",
        "policy.denied",
        "policy.override.required",
        "policy.risk.detected",
        "consolidation.completed",
        "consolidation.failed",
        "elimination.generated",
        "intercompany.created",
        "intercompany.mismatch.detected",
        "entity.closed",
        "compliance.alert.generated",
    }:
        _consume_governance_event(envelope)
    elif queue.endswith("workflow.execution"):
        workflow_consumer.consume_workflow_execution_event(envelope)
    elif queue.endswith("workflow.sla"):
        workflow_consumer.consume_workflow_sla_event(envelope)
    elif queue.endswith("workflow.escalations"):
        workflow_consumer.consume_workflow_escalation_event(envelope)
    elif queue.endswith("workflow.retries"):
        workflow_consumer.consume_workflow_execution_event(envelope)
    elif queue.endswith("workflow.approvals"):
        workflow_consumer.consume_workflow_approval_event(envelope)
    elif queue.endswith("ai.ocr"):
        finance_os_consumer.consume_ocr_event(envelope)
    elif queue.endswith("ai.reconciliation") or queue.endswith("ai.risk") or queue.endswith("ai.forecasting"):
        finance_os_consumer.consume_ai_queue_event(envelope)
    elif queue.endswith("ai.memory"):
        finance_os_consumer.consume_memory_event(envelope)
    elif (
        queue.endswith("integration.gst")
        or queue.endswith("integration.bank")
        or queue.endswith("integration.webhooks")
        or queue.endswith("integration.email")
    ):
        _consume_integration_event(envelope)
    elif (
        queue.endswith("notifications.email")
        or queue.endswith("notifications.whatsapp")
        or queue.endswith("notifications.push")
    ):
        _consume_notification_event(envelope, queue=queue)
    elif queue.endswith("reports.generate") or queue.endswith("reports.refresh"):
        _consume_reports_event(envelope)
    elif "scheduler" in str(envelope.get("event_type", "")):
        _consume_scheduler_event(envelope)
    _consume_document_intelligence_event(envelope)
    _consume_document_security_event(envelope)
    erp_consumer.consume_coa_events(envelope)
    workflow_consumer.consume_workflow_intelligence(envelope)
    finance_os_consumer.consume_m25_invoice_pipeline(envelope)
    finance_os_consumer.consume_memory_ingestion(envelope)
    finance_os_consumer.consume_graph_ingestion(envelope)
    finance_os_consumer.consume_agents_trigger(envelope)
    finance_os_consumer.consume_goal_triggers(envelope)
    finance_os_consumer.consume_m38_scheduler(envelope)
    finance_os_consumer.consume_forecasting_refresh(envelope)
    finance_os_consumer.consume_reporting_refresh(envelope)
    finance_os_consumer.consume_analytics_refresh(envelope)
    finance_os_consumer.consume_audit_explorer_materialize(envelope)
    finance_os_consumer.consume_invoice_predicted(envelope)
    finance_os_consumer.consume_invoice_ai_reviewed(envelope)
    workflow_consumer.consume_workflow_system_task_gl_post(envelope)
    erp_consumer.consume_journal_events(envelope)
    erp_consumer.consume_treasury_events(envelope)
    erp_consumer.consume_tax_events(envelope)
    erp_consumer.consume_fiscal_events(envelope)
    erp_consumer.consume_procurement_events(envelope)
    erp_consumer.consume_expense_events(envelope)
    erp_consumer.consume_asset_events(envelope)
    erp_consumer.consume_inventory_events(envelope)
    erp_consumer.consume_ar_events(envelope)
    _push_document_realtime(envelope)
    try:
        from app.modules.platform.notifications.services.notification_service import notification_service

        if (
            notification_service.schema_ready()
            and not queue.endswith("audit.persist")
            and _should_route_domain_notification(envelope, queue)
        ):
            notification_service.handle_event_envelope(envelope)
    except Exception:
        pass
    log_event("event.consumer.processed", queue=queue, event_type=envelope.get("event_type", ""))
