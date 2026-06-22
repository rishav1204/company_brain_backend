from __future__ import annotations

from app.modules.finance_os.graph.ai.knowledge_extractor import extract_from_event
from app.modules.finance_os.graph.engine.graph_sync_engine import apply_mutations
from app.modules.finance_os.graph.events.graph_events import emit_graph_updated, emit_root_cause_generated
from app.modules.finance_os.graph.repositories.sync_audit_repository import sync_audit_repository
from app.modules.finance_os.graph.ai.root_cause_detector import detect_root_cause
from app.modules.platform.billing.billing_hooks import billing_ai_operation


class GraphIngestionPipeline:
    def run_from_event(self, envelope: dict) -> dict | None:
        org_id = str(envelope.get("org_id", ""))
        if not org_id:
            return None
        with billing_ai_operation(org_id, feature="graph_engine", operation_code="graph_ingest"):
            return self._run_from_event_inner(envelope)

    def _run_from_event_inner(self, envelope: dict) -> dict | None:
        event_type = str(envelope.get("event_type", ""))
        payload = envelope.get("payload") or {}
        org_id = str(envelope.get("org_id", ""))
        trace_id = str(envelope.get("trace_id") or "")
        if not org_id:
            return None
        extracted = extract_from_event(event_type, payload)
        if not extracted:
            return None
        entity_id = extracted.get("entity_id")
        if entity_id and sync_audit_repository.exists_for_event(org_id, source_event_type=event_type, entity_id=entity_id):
            return {"status": "skipped", "reason": "duplicate"}
        result = apply_mutations(org_id, extracted)
        sync_audit_repository.create(
            org_id,
            source_event_type=event_type,
            entity_type=extracted.get("entity_type"),
            entity_id=entity_id,
            mutation_type="relationship_upsert",
            status="success" if result.get("status") == "ok" else "partial",
            trace_id=trace_id,
            metadata={"nodes": result.get("nodes_applied"), "edges": result.get("edges_applied")},
        )
        emit_graph_updated(
            org_id,
            {"entity_type": extracted.get("entity_type"), "entity_id": entity_id, **result},
            trace_id=trace_id,
        )
        if entity_id:
            rc = detect_root_cause(org_id, str(entity_id))
            if rc.get("detected"):
                emit_root_cause_generated(org_id, rc, trace_id=trace_id)
        return result

    def run_manual(self, org_id: str, *, mutations: dict, trace_id: str | None = None) -> dict:
        result = apply_mutations(org_id, mutations)
        sync_audit_repository.create(
            org_id,
            source_event_type="manual",
            entity_type=mutations.get("entity_type"),
            entity_id=mutations.get("entity_id"),
            mutation_type="manual_upsert",
            status="success",
            trace_id=trace_id,
            metadata=result,
        )
        emit_graph_updated(org_id, result, trace_id=trace_id)
        return result


graph_ingestion_pipeline = GraphIngestionPipeline()
