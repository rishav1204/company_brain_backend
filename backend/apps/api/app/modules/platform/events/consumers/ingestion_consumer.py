"""Ingestion, processing, and graph upsert event consumers."""
from __future__ import annotations

from app.modules.platform.events.consumers._helpers import publish_child_event
from app.services.canonicalization_service import normalize_connector_payload
from app.services.connectors import run_connector
from app.services.embedding_worker_service import ingest_document_for_embedding
from app.services.graph_extraction_service import extract_relationships_for_org
from app.services.repositories import sources_repo


def consume_ingestion_event(envelope: dict) -> None:
    payload = envelope.get("payload", {})
    org_id = str(envelope.get("org_id", ""))
    event_type = str(envelope.get("event_type", ""))
    if event_type != "source.sync.started":
        return
    source_id = str(payload.get("source_id", ""))
    source = sources_repo.get_source(org_id=org_id, source_id=source_id)
    if not source:
        return
    connector = str(source.get("source_type", ""))
    result = run_connector(org_id=org_id, connector=connector, mode="polling")
    status_event = "source.sync.completed" if result.status == "completed" else "source.sync.failed"
    publish_child_event(
        envelope,
        event_type=status_event,
        org_id=org_id,
        source="worker.ingestion",
        payload={"source_id": source_id, "connector": connector, "detail": result.detail},
    )
    if result.status == "completed" and connector in {"docs", "erp", "crm", "ticketing"}:
        normalized = normalize_connector_payload(
            org_id=org_id,
            connector=connector,
            payload={
                "connector": connector,
                "amount": payload.get("amount"),
                "entity_name": payload.get("entity_name", connector),
            },
        )
        publish_child_event(
            envelope,
            event_type="entity.resolved",
            org_id=org_id,
            source="worker.ingestion",
            payload={"connector": connector, "normalized": normalized},
        )
        ingest_document_for_embedding(
            org_id=org_id,
            source_id=source_id,
            title=f"{connector} sync payload",
            content=f"Connector {connector} sync completed with detail: {result.detail}",
            doc_type="connector_sync",
            permission_ref=sources_repo.get_source_ref(org_id=org_id, source_id=source_id),
        )


def consume_chunk_processing_event(envelope: dict) -> None:
    payload = envelope.get("payload", {})
    org_id = str(envelope.get("org_id", ""))
    source_id = str(payload.get("source_id", ""))
    content = str(payload.get("content", "")).strip()
    if not source_id or not content:
        return
    ingest_document_for_embedding(
        org_id=org_id,
        source_id=source_id,
        title=str(payload.get("title", "chunk-processed")),
        content=content,
        doc_type=str(payload.get("doc_type", "connector_sync")),
        permission_ref=sources_repo.get_source_ref(org_id=org_id, source_id=source_id),
    )


def consume_extract_event(envelope: dict) -> None:
    payload = envelope.get("payload", {})
    org_id = str(envelope.get("org_id", ""))
    connector = str(payload.get("connector", ""))
    normalize_connector_payload(org_id=org_id, connector=connector or "docs", payload=payload)
    publish_child_event(
        envelope,
        event_type="graph.upsert.requested",
        org_id=org_id,
        source="worker.extract",
        payload={"connector": connector},
    )


def consume_graph_event(envelope: dict) -> None:
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload") or {}
    if payload.get("entity_id") or payload.get("entity_type"):
        try:
            from app.modules.finance_os.graph.pipelines.graph_ingestion_pipeline import graph_ingestion_pipeline

            graph_ingestion_pipeline.run_from_event(envelope)
            return
        except Exception:
            pass
    extract_relationships_for_org(org_id=org_id)


def consume_retry_event(envelope: dict) -> None:
    from app.services.scheduler_service import run_scheduled_jobs_once

    org_id = str(envelope.get("org_id", ""))
    run_scheduled_jobs_once(org_id=org_id)
