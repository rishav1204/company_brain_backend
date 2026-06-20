from __future__ import annotations

from app.modules.finance_os.graph.engine.graph_builder import build_mutation, merge_mutations
from app.modules.finance_os.graph.engine.lineage_engine import format_lineage_paths, format_neighbors
from app.modules.finance_os.graph.engine.graph_sync_engine import apply_mutations
from app.modules.finance_os.graph.ai.knowledge_extractor import NOISE_EVENTS, EXTRACTOR_MAP, extract_from_event
from app.modules.finance_os.graph.events.graph_events import (
    GRAPH_UPDATED,
    GRAPH_LINEAGE_GENERATED,
    GRAPH_DEPENDENCY_DETECTED,
    GRAPH_ROOT_CAUSE_GENERATED,
)
from app.modules.finance_os.graph.extractors import (
    invoice_extractor,
    payment_extractor,
    journal_extractor,
    workflow_extractor,
    reconciliation_extractor,
    treasury_extractor,
    compliance_extractor,
    asset_extractor,
)
from app.services.neo4j_service import Neo4jService


def test_allowed_labels_include_journal() -> None:
    assert "Journal" in Neo4jService.ALLOWED_LABELS


def test_allowed_labels_include_gst_return() -> None:
    assert "GSTReturn" in Neo4jService.ALLOWED_LABELS


def test_allowed_labels_include_reconciliation() -> None:
    assert "Reconciliation" in Neo4jService.ALLOWED_LABELS


def test_allowed_labels_include_bank_transaction() -> None:
    assert "BankTransaction" in Neo4jService.ALLOWED_LABELS


def test_allowed_labels_include_compliance() -> None:
    assert "Compliance" in Neo4jService.ALLOWED_LABELS


def test_allowed_labels_include_asset() -> None:
    assert "Asset" in Neo4jService.ALLOWED_LABELS


def test_allowed_rel_generated() -> None:
    assert "GENERATED" in Neo4jService.ALLOWED_REL_TYPES


def test_allowed_rel_settled_by() -> None:
    assert "SETTLED_BY" in Neo4jService.ALLOWED_REL_TYPES


def test_allowed_rel_reported_in() -> None:
    assert "REPORTED_IN" in Neo4jService.ALLOWED_REL_TYPES


def test_allowed_rel_matched_in() -> None:
    assert "MATCHED_IN" in Neo4jService.ALLOWED_REL_TYPES


def test_allowed_rel_filed_as() -> None:
    assert "FILED_AS" in Neo4jService.ALLOWED_REL_TYPES


def test_allowed_rel_capitalized_as() -> None:
    assert "CAPITALIZED_AS" in Neo4jService.ALLOWED_REL_TYPES


def test_format_neighbors() -> None:
    rows = [{"from_label": "Vendor", "from_id": "v1", "rel_type": "ISSUED", "to_label": "Invoice", "to_id": "i1"}]
    assert "Vendor:v1" in format_neighbors(rows)[0]


def test_format_lineage_paths() -> None:
    rows = [{"start_label": "Invoice", "start_id": "i1", "rel_types": ["PAID_BY"], "end_label": "Payment", "end_id": "p1"}]
    assert "Invoice:i1" in format_lineage_paths(rows)[0]


def test_build_mutation() -> None:
    m = build_mutation(nodes=[{"label": "Invoice", "id": "1"}], edges=[])
    assert len(m["nodes"]) == 1


def test_merge_mutations() -> None:
    a = build_mutation(nodes=[{"label": "A", "id": "1"}])
    b = build_mutation(edges=[{"from_label": "A", "from_id": "1", "rel_type": "ISSUED", "to_label": "B", "to_id": "2"}])
    merged = merge_mutations(a, b)
    assert len(merged["nodes"]) == 1
    assert len(merged["edges"]) == 1


def test_noise_event_rejected() -> None:
    assert "document.uploaded" in NOISE_EVENTS
    assert extract_from_event("document.uploaded", {}) is None


def test_invoice_created_extract() -> None:
    result = invoice_extractor.extract("erp.invoice.created", {"invoice_id": "inv-1", "vendor_id": "v-1"})
    assert result is not None
    assert any(e["rel_type"] == "ISSUED" for e in result["edges"])


def test_invoice_requires_approval() -> None:
    result = invoice_extractor.extract(
        "approval.requested", {"invoice_id": "inv-1", "workflow_id": "wf-1"}
    )
    assert result is not None
    assert any(e["rel_type"] == "REQUIRES_APPROVAL" for e in result["edges"])


def test_invoice_anomaly_extract() -> None:
    result = invoice_extractor.extract("invoice.anomaly_detected", {"invoice_id": "inv-1"})
    assert result is not None


def test_payment_extract() -> None:
    result = payment_extractor.extract("payment.executed", {"payment_id": "p-1", "invoice_id": "inv-1"})
    assert result is not None
    assert any(e["rel_type"] == "PAID_BY" for e in result["edges"])


def test_journal_extract() -> None:
    result = journal_extractor.extract("journal.posted", {"journal_id": "j-1", "source_id": "inv-1"})
    assert result is not None
    assert any(e["rel_type"] == "GENERATED" for e in result["edges"])


def test_workflow_approval_extract() -> None:
    result = workflow_extractor.extract(
        "approval.completed",
        {"workflow_id": "wf-1", "approver_id": "u-1", "object_id": "inv-1"},
    )
    assert result is not None


def test_workflow_blocked_extract() -> None:
    result = workflow_extractor.extract("workflow.failed", {"workflow_id": "wf-1"})
    assert result is not None
    assert any(e["rel_type"] == "BLOCKED_BY" for e in result["edges"])


def test_workflow_precedes_extract() -> None:
    result = workflow_extractor.extract(
        "workflow.completed", {"workflow_id": "wf-2", "prior_workflow_id": "wf-1"}
    )
    assert result is not None
    assert any(e["rel_type"] == "PRECEDES" for e in result["edges"])


def test_reconciliation_extract() -> None:
    result = reconciliation_extractor.extract(
        "reconciliation.completed", {"reconciliation_id": "r-1", "bank_transaction_id": "bt-1"}
    )
    assert result is not None


def test_treasury_bank_extract() -> None:
    result = treasury_extractor.extract(
        "bank.transaction.imported", {"bank_transaction_id": "bt-1", "payment_id": "p-1"}
    )
    assert result is not None
    assert any(e["rel_type"] == "SETTLED_BY" for e in result["edges"])


def test_compliance_gst_extract() -> None:
    result = compliance_extractor.extract(
        "erp.gst.return.generated", {"gst_return_id": "gst-1", "invoice_id": "inv-1"}
    )
    assert result is not None
    assert any(e["rel_type"] == "REPORTED_IN" for e in result["edges"])


def test_compliance_filing_extract() -> None:
    result = compliance_extractor.extract(
        "compliance.completed", {"gst_return_id": "gst-1", "compliance_id": "c-1"}
    )
    assert result is not None
    assert any(e["rel_type"] == "FILED_AS" for e in result["edges"])


def test_asset_extract() -> None:
    result = asset_extractor.extract("erp.asset.capitalized", {"asset_id": "a-1", "invoice_id": "inv-1"})
    assert result is not None
    assert any(e["rel_type"] == "CAPITALIZED_AS" for e in result["edges"])


def test_extractor_map_has_payment() -> None:
    assert "payment.executed" in EXTRACTOR_MAP


def test_extractor_map_has_journal() -> None:
    assert "journal.posted" in EXTRACTOR_MAP


def test_event_constants() -> None:
    assert GRAPH_UPDATED == "graph.updated"
    assert GRAPH_LINEAGE_GENERATED == "graph.lineage.generated"
    assert GRAPH_DEPENDENCY_DETECTED == "graph.dependency.detected"
    assert GRAPH_ROOT_CAUSE_GENERATED == "graph.root_cause.generated"


def test_graph_guard_read() -> None:
    from app.modules.finance_os.graph.security.graph_guard import require_graph_read

    require_graph_read({"permissions": ["graph.read"]})


def test_graph_guard_write() -> None:
    from app.modules.finance_os.graph.security.graph_guard import require_graph_write

    require_graph_write({"permissions": ["graph.write"]})


def test_router_prefix() -> None:
    assert "/finance-os/graph" == "/finance-os/graph"


def test_m25_bridge_import() -> None:
    from app.modules.finance_os.graph.bridges.m25_bridge import vendor_ecosystem

    assert callable(vendor_ecosystem)


def test_m26_bridge_import() -> None:
    from app.modules.finance_os.graph.bridges.m26_bridge import annotate_workflow_bottleneck

    assert callable(annotate_workflow_bottleneck)


def test_m23_bridge_import() -> None:
    from app.modules.finance_os.graph.bridges.m23_bridge import reconciliation_lineage

    assert callable(reconciliation_lineage)


def test_m24_bridge_import() -> None:
    from app.modules.finance_os.graph.bridges.m24_bridge import cash_chain

    assert callable(cash_chain)


def test_memory_bridge_import() -> None:
    from app.modules.finance_os.graph.bridges.memory_bridge import write_causal_summary

    assert callable(write_causal_summary)


def test_retrieval_bridge_import() -> None:
    from app.modules.finance_os.graph.bridges.retrieval_bridge import graph_trace_for_subject

    assert callable(graph_trace_for_subject)


def test_dependency_analyzer_import() -> None:
    from app.modules.finance_os.graph.ai.dependency_analyzer import analyze_dependencies

    assert callable(analyze_dependencies)


def test_root_cause_detector_import() -> None:
    from app.modules.finance_os.graph.ai.root_cause_detector import detect_root_cause

    assert callable(detect_root_cause)


def test_graph_copilot_import() -> None:
    from app.modules.finance_os.graph.ai.graph_copilot import answer

    assert callable(answer)


def test_graph_reasoner_import() -> None:
    from app.modules.finance_os.graph.ai.graph_reasoner import build_context

    assert callable(build_context)


def test_ingestion_pipeline_import() -> None:
    from app.modules.finance_os.graph.pipelines.graph_ingestion_pipeline import graph_ingestion_pipeline

    assert hasattr(graph_ingestion_pipeline, "run_from_event")


def test_manual_payload_extract() -> None:
    result = extract_from_event(
        "graph.updated",
        {"nodes": [{"label": "Invoice", "id": "1"}], "edges": [], "entity_id": "1"},
    )
    assert result is not None


def test_payment_no_id_skipped() -> None:
    assert payment_extractor.extract("payment.executed", {}) is None


def test_journal_no_id_skipped() -> None:
    assert journal_extractor.extract("journal.posted", {}) is None


def test_reconciliation_minimal() -> None:
    assert reconciliation_extractor.extract("reconciliation.completed", {}) is None


def test_resolve_blocked_by_target() -> None:
    from app.services.graph_service import _resolve_to_label

    assert _resolve_to_label("BLOCKED_BY", "Workflow") == "Incident"


def test_apply_mutations_empty() -> None:
    result = apply_mutations("org", {"nodes": [], "edges": []})
    assert result["nodes_applied"] == 0


def test_get_lifecycle_import() -> None:
    from app.modules.finance_os.graph.engine.lineage_engine import get_lifecycle

    assert callable(get_lifecycle)


def test_get_dependents_import() -> None:
    from app.modules.finance_os.graph.engine.dependency_engine import get_dependents

    assert callable(get_dependents)


def test_explain_chain_import() -> None:
    from app.modules.finance_os.graph.engine.causality_engine import explain_chain

    assert callable(explain_chain)


def test_visualization_service_import() -> None:
    from app.modules.finance_os.graph.services.visualization_service import visualization

    assert callable(visualization)


def test_graph_search_service_import() -> None:
    from app.modules.finance_os.graph.services.graph_search_service import search

    assert callable(search)


def test_projection_service_import() -> None:
    from app.modules.finance_os.graph.services.graph_projection_service import rebuild_org

    assert callable(rebuild_org)
