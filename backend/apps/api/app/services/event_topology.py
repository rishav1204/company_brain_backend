from app.core.config import settings
from app.modules.platform.events.bus.topology import platform_queue_groups, route_platform_event


def queue_groups() -> dict[str, str]:
    return platform_queue_groups()


def service_boundaries() -> dict[str, list[str]]:
    groups = queue_groups()
    return {
        "ingestion_service": [groups["ingestion.sync"], groups["ingestion.retry"]],
        "processing_service": [groups["processing.chunk"], groups["processing.embed"], groups["processing.extract"]],
        "graph_service": [groups["graph.upsert"]],
        "memory_service": [groups["memory.write"], groups["retrieval.precompute"], groups["ai.memory"]],
        "agent_runner_service": [groups["agent.run"], groups["ai.ocr"], groups["ai.risk"], groups["ai.reconciliation"]],
        "execution_service": [
            groups["agent.action"],
            groups["notifications.dispatch"],
            groups["notifications.email"],
            groups["notifications.whatsapp"],
            groups["notifications.push"],
        ],
        "audit_service": [groups["audit.persist"]],
        "workflow_service": [
            groups["workflow.execution"],
            groups["workflow.approvals"],
            groups["workflow.escalations"],
            groups["workflow.sla"],
            groups["workflow.retries"],
        ],
        "integration_service": [
            groups["integration.gst"],
            groups["integration.bank"],
            groups["integration.webhooks"],
            groups["integration.email"],
        ],
        "reporting_service": [groups["reports.generate"], groups["reports.refresh"]],
    }


def finance_topics() -> dict[str, str]:
    groups = queue_groups()
    return {
        "finance.ingest": groups["ingestion.sync"],
        "finance.process": groups["processing.chunk"],
        "finance.agent": groups["agent.run"],
        "finance.action": groups["agent.action"],
        "finance.audit": groups["audit.persist"],
        "finance.erp": groups["workflow.execution"],
        "finance.workflow": groups["workflow.execution"],
    }


def topic_for_event_type(event_type: str) -> str:
    if event_type.startswith("erp.") or event_type in {"invoice.created", "payment.completed", "journal.posted"}:
        return "finance.erp"
    if event_type.startswith("workflow.") or event_type.startswith("approval.") or event_type.startswith("sla."):
        return "finance.workflow"
    if event_type.startswith("source.sync"):
        return "finance.ingest"
    if (
        event_type.startswith("document.")
        or event_type.startswith("chunk.")
        or event_type.startswith("entity.")
        or event_type.startswith("memory.")
        or event_type.startswith("decision.")
    ):
        return "finance.process"
    if event_type.startswith("agent.run") or event_type.startswith("ai.") or event_type.startswith("invoice.ai"):
        return "finance.agent"
    if event_type.startswith("agent.action"):
        return "finance.action"
    if event_type.startswith("policy.") or event_type.startswith("audit."):
        return "finance.audit"
    return "finance.audit"


def queue_dlq_name(queue_name: str) -> str:
    return f"{queue_name}.dlq"


def route_for_event_type(event_type: str) -> str:
    return route_platform_event(event_type)


def route_for_envelope(envelope: dict) -> str:
    topic = str(envelope.get("topic", "")).strip()
    topics = finance_topics()
    if topic and topic in topics:
        return topics[topic]
    return route_for_event_type(str(envelope.get("event_type", "")))
