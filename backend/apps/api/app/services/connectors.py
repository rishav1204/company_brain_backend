from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json

from app.services.canonicalization_service import normalize_connector_payload
from app.services.event_bus import event_bus
from app.services.integration_service import integration_service
from app.services.logger import log_event
from app.services.repositories import ingestion_repo


@dataclass
class ConnectorResult:
    connector: str
    status: str
    records_ingested: int
    detail: str


def _connector_dataset(connector: str, mode: str, source_id: str | None, cursor_ref: str | None) -> list[dict]:
    base = f"{connector}:{mode}:{source_id or 'na'}:{cursor_ref or 'start'}"
    now = datetime.now(timezone.utc).date().isoformat()
    return [
        {
            "external_record_id": f"{base}:1",
            "entity_name": f"{connector}-entity-a",
            "external_ref": f"{connector.upper()}-A",
            "amount": 1250.0,
            "due_date": now,
            "risk_tier": "medium",
            "payment_terms": "Net 30",
            "invoice_type": "ap" if connector != "crm" else "ar",
            "po_number": f"PO-{connector.upper()}-A",
            "contract_number": f"CTR-{connector.upper()}-A",
            "account_code": "5000" if connector == "erp" else None,
            "payment_date": now if connector == "bank" else None,
        },
        {
            "external_record_id": f"{base}:2",
            "entity_name": f"{connector}-entity-b",
            "external_ref": f"{connector.upper()}-B",
            "amount": 420.0,
            "due_date": now,
            "risk_tier": "low",
            "payment_terms": "Net 15",
            "invoice_type": "ap" if connector != "crm" else "ar",
        },
    ]


def _payload_hash(record: dict) -> str:
    return hashlib.sha256(json.dumps(record, sort_keys=True).encode("utf-8")).hexdigest()


def run_connector(org_id: str, connector: str, mode: str, source_id: str | None = None) -> ConnectorResult:
    supported = {"erp", "bank", "crm", "docs", "ticketing", "slack", "email", "jira", "linear"}
    if connector not in supported:
        return ConnectorResult(connector=connector, status="error", records_ingested=0, detail="connector_not_supported")
    prev_state = ingestion_repo.get_connector_sync_state(org_id=org_id, connector=connector, source_id=source_id, mode=mode)
    cursor_ref = str((prev_state or {}).get("cursor_ref") or "")
    timestamp = datetime.now(timezone.utc).isoformat()
    if connector == "erp":
        result = integration_service.push_erp({"mode": mode, "timestamp": timestamp})
    elif connector == "bank":
        result = integration_service.push_bank({"mode": mode, "timestamp": timestamp})
    elif connector == "crm":
        result = integration_service.push_crm({"mode": mode, "timestamp": timestamp})
    elif connector == "docs":
        result = integration_service.push_docs({"mode": mode, "timestamp": timestamp})
    elif connector == "ticketing":
        result = integration_service.push_ticketing({"mode": mode, "timestamp": timestamp})
    elif connector == "slack":
        result = integration_service.send_slack(channel="#finance-alerts", text=f"Connector run via {mode} at {timestamp}")
    elif connector == "email":
        result = integration_service.send_email(
            to="finance-ops@example.com",
            subject="Connector run notification",
            body=f"Connector mode={mode} completed at {timestamp}",
        )
    elif connector == "jira":
        result = integration_service.create_jira_issue(
            summary=f"Connector run ({mode})",
            description=f"Connector executed at {timestamp}",
        )
    else:
        result = integration_service.create_linear_issue(
            title=f"Connector run ({mode})",
            description=f"Connector executed at {timestamp}",
        )
    log_event("connector.run", connector=connector, mode=mode, status=result.status, detail=result.detail)
    if result.status != "completed":
        return ConnectorResult(
            connector=connector,
            status="error",
            records_ingested=0,
            detail=result.detail,
        )
    records_ingested = 0
    new_cursor = f"{connector}:{int(datetime.now(timezone.utc).timestamp())}"
    if connector in {"erp", "bank", "crm", "docs", "ticketing"}:
        dataset = _connector_dataset(connector=connector, mode=mode, source_id=source_id, cursor_ref=cursor_ref or None)
        for record in dataset:
            external_record_id = str(record.get("external_record_id", "")).strip()
            if not external_record_id:
                continue
            if ingestion_repo.has_processed_connector_record(
                org_id=org_id,
                connector=connector,
                source_id=source_id,
                external_record_id=external_record_id,
            ):
                continue
            normalized = normalize_connector_payload(org_id=org_id, connector=connector, payload=record)
            entity_id = str((normalized.get("entity") or {}).get("id", "")).strip() or None
            ingestion_repo.mark_connector_record_processed(
                org_id=org_id,
                connector=connector,
                source_id=source_id,
                external_record_id=external_record_id,
                payload_hash=_payload_hash(record),
                normalized_ref=entity_id,
            )
            records_ingested += 1
        ingestion_repo.upsert_connector_sync_state(
            org_id=org_id,
            connector=connector,
            source_id=source_id,
            mode=mode,
            cursor_ref=new_cursor,
            metadata_jsonb={
                "last_status": "completed",
                "records_ingested": records_ingested,
                "previous_cursor": cursor_ref,
                "updated_at": timestamp,
            },
        )
    event_bus.publish(
        event_type="document.ingested",
        org_id=org_id,
        source=f"connector.{connector}",
        trace_id=f"connector-{connector}-{int(datetime.now(timezone.utc).timestamp())}",
        payload={
            "connector": connector,
            "mode": mode,
            "source_id": source_id,
            "cursor_ref": new_cursor,
            "records_ingested": records_ingested,
            "detail": result.detail,
        },
    )
    return ConnectorResult(
        connector=connector,
        status="completed",
        records_ingested=records_ingested,
        detail=f"{connector} integration completed via {mode} at {timestamp}",
    )
