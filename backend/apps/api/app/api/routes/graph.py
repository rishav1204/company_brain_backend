"""Legacy graph routes — prefer /finance-os/graph/* (see LEGACY_ROUTE_MIGRATION.md)."""
from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.finance_os.graph.services.finance_graph_service import get_entity
from app.modules.finance_os.graph.services.graph_projection_service import rebuild_org
from app.modules.finance_os.graph.services.lineage_service import lineage
from app.modules.finance_os.graph.services.dependency_service import dependencies
from app.modules.finance_os.graph.services.causality_service import root_cause
from app.modules.finance_os.graph.services.graph_search_service import search
from app.services.graph_service import query_related_entities
from app.services.neo4j_service import neo4j_service

router = APIRouter(tags=["graph"])


@router.post("/graph/bootstrap")
def graph_bootstrap(context=Depends(build_request_context)) -> dict:
    result = neo4j_service.bootstrap_schema()
    return {
        "request_id": context.request_id,
        "result": result,
        "confidence": 0.93,
        "verification_status": "graph_schema_bootstrap",
    }


@router.post("/graph/extract")
def graph_extract(context=Depends(build_request_context)) -> dict:
    result = rebuild_org(context.org_id, trace_id=context.request_id)
    return {
        "request_id": context.request_id,
        "result": result,
        "confidence": 0.92,
        "verification_status": "graph_extraction_completed",
    }


@router.get("/graph/queries/invoice-exceptions")
def graph_invoice_exceptions(subject_ref: str | None = None, context=Depends(build_request_context)) -> dict:
    trace = query_related_entities(org_id=context.org_id, subject_ref=subject_ref)
    return {
        "request_id": context.request_id,
        "graph_trace": trace,
        "confidence": 0.9,
        "verification_status": "graph_query_completed",
    }


@router.get("/graph/queries/close-root-cause")
def graph_close_root_cause(limit: int = 20, context=Depends(build_request_context)) -> dict:
    rows = neo4j_service.query_root_cause_close_delays(org_id=context.org_id, limit=limit)
    return {
        "request_id": context.request_id,
        "rows": rows,
        "confidence": 0.91,
        "verification_status": "graph_root_cause_query_completed",
    }


@router.get("/graph/queries/ap-patterns")
def graph_ap_patterns(limit: int = 20, context=Depends(build_request_context)) -> dict:
    rows = neo4j_service.query_ap_exception_patterns(org_id=context.org_id, limit=limit)
    return {
        "request_id": context.request_id,
        "rows": rows,
        "confidence": 0.91,
        "verification_status": "graph_ap_patterns_query_completed",
    }


@router.get("/graph/queries/decision-impact")
def graph_decision_impact(limit: int = 20, context=Depends(build_request_context)) -> dict:
    rows = neo4j_service.query_decision_impact_paths(org_id=context.org_id, limit=limit)
    return {
        "request_id": context.request_id,
        "rows": rows,
        "confidence": 0.91,
        "verification_status": "graph_decision_impact_query_completed",
    }
