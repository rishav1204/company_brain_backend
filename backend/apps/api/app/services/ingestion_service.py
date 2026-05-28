from app.services.event_bus import event_bus
from app.services.repositories import ingestion_repo


class ConnectorMode:
    WEBHOOK = "webhook"
    POLLING = "polling"
    CDC = "cdc"


def score_source_reliability(success_count: int, failure_count: int) -> float:
    total = success_count + failure_count
    if total <= 0:
        return 0.5
    return round(success_count / total, 4)


def start_ingestion_run(
    org_id: str,
    source_id: str,
    trigger_mode: str,
    trace_id: str,
    principal: dict | None = None,
) -> dict:
    row = ingestion_repo.create_run(org_id=org_id, source_id=source_id, status="started")
    event_bus.publish(
        event_type="source.sync.started",
        org_id=org_id,
        source="service.ingestion",
        trace_id=trace_id,
        payload={"source_id": source_id, "run_id": row["id"], "trigger_mode": trigger_mode},
        principal=principal,
    )
    return row


def complete_ingestion_run(
    org_id: str,
    run_id: str,
    trace_id: str,
    success: bool,
    error_summary: str | None = None,
    principal: dict | None = None,
) -> dict | None:
    row = ingestion_repo.complete_run(org_id=org_id, run_id=run_id, success=success, error_summary=error_summary)
    if row is None:
        return None
    event_bus.publish(
        event_type="source.sync.completed" if success else "source.sync.failed",
        org_id=org_id,
        source="service.ingestion",
        trace_id=trace_id,
        payload={"run_id": run_id, "error_summary": error_summary},
        principal=principal,
    )
    return row
