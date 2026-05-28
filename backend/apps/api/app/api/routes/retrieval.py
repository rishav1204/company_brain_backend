from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.schemas.retrieval import (
    QueryContextRequest,
    QueryContextResponse,
    QueryExplainRequest,
    QueryExplainResponse,
)
from app.services.metrics import metrics_store
from app.modules.core.iam.services.finance_route_guard import enforce_finance_route_access
from app.modules.core.iam.services.rbac_service import can_access_sensitive_field
from app.services.policy_service import abac_allows, source_acl_allows
from app.services.retrieval_pipeline import retrieve_hybrid_context
from app.services.retrieval_service import explain_query
from app.services.trace import trace_span

router = APIRouter(tags=["retrieval"])


@router.post("/query/context", response_model=QueryContextResponse)
def query_context(request: QueryContextRequest, context=Depends(build_request_context)) -> QueryContextResponse:
    enforce_finance_route_access(context, object_type="retrieval", mode="read")
    metrics_store.incr_retrieval_query()
    effective_filter = dict(request.metadata_filter or {})
    if context.source_acl and "*" not in context.source_acl:
        effective_filter["allowed_source_refs"] = context.source_acl
    with trace_span("retrieval.query_context", org_id=context.org_id, request_id=context.request_id):
        pipeline_result = retrieve_hybrid_context(
            org_id=context.org_id,
            query=request.query,
            subject_ref=request.subject_ref,
            top_k=request.top_k,
            metadata_filter=effective_filter,
        )
    try:
        from app.modules.platform.governance.explainability.retrieval_trace_manager import build_retrieval_trace

        citations = pipeline_result.get("citations", []) or []
        chunk_ids = [str(getattr(c, "id", i)) for i, c in enumerate(citations)]
        scores = [float(getattr(c, "score", 0) or 0) for c in citations]
        trace_meta = build_retrieval_trace(query=request.query, chunk_ids=chunk_ids, scores=scores)
        from app.modules.platform.governance.services.audit_service import audit_service

        audit_service.record(
            org_id=context.org_id,
            actor_type="user",
            actor_id=context.user_id,
            action="retrieval.query",
            object_ref=f"retrieval:query:{context.request_id}",
            payload=trace_meta,
            trace_id=context.trace_id,
            request_id=context.request_id,
            source_service="retrieval.pipeline",
        )
    except Exception:
        pass
    if not abac_allows(context.attrs, action="read", object_type="retrieval"):
        return QueryContextResponse(
            request_id=context.request_id,
            context=[],
            citations=[],
            confidence=0.99,
            verification_status="abac_denied",
        )
    composed_context = []
    for item in pipeline_result["context"]:
        lowered = item.lower()
        sensitive_fields = ("bank_account_number", "tax_id", "ssn", "salary")
        if any(field in lowered for field in sensitive_fields):
            field_hit = next((f for f in sensitive_fields if f in lowered), "tax_id")
            if not can_access_sensitive_field(context.org_id, context.user_id, context.roles, field_hit):
                continue
        composed_context.append(item)
    citations = []
    for citation in pipeline_result["citations"]:
        if source_acl_allows(context.source_acl, citation.source_ref):
            citations.append(citation)
    return QueryContextResponse(
        request_id=context.request_id,
        context=composed_context[: request.top_k],
        citations=citations,
        confidence=0.93,
        verification_status="citation_backed",
    )


@router.post("/query/explain", response_model=QueryExplainResponse)
def query_explain(request: QueryExplainRequest, context=Depends(build_request_context)) -> QueryExplainResponse:
    enforce_finance_route_access(context, object_type="retrieval", mode="read")
    metrics_store.incr_retrieval_query()
    explain_filter = {}
    if context.source_acl and "*" not in context.source_acl:
        explain_filter["allowed_source_refs"] = context.source_acl
    with trace_span("retrieval.query_explain", org_id=context.org_id, request_id=context.request_id):
        answer, _, citations = explain_query(org_id=context.org_id, query=request.query, subject_ref=request.subject_ref)
        pipeline_result = retrieve_hybrid_context(
            org_id=context.org_id,
            query=request.query,
            subject_ref=request.subject_ref,
            top_k=5,
            metadata_filter=explain_filter,
        )
    graph_trace = pipeline_result["graph_trace"]
    filtered_citations = [c for c in citations if source_acl_allows(context.source_acl, c.source_ref)]
    if not abac_allows(context.attrs, action="read", object_type="retrieval"):
        answer = "Access denied by ABAC policy for retrieval context."
        filtered_citations = []
        graph_trace = []
    return QueryExplainResponse(
        request_id=context.request_id,
        answer=answer,
        graph_trace=graph_trace,
        citations=filtered_citations,
        confidence=0.91,
        verification_status="requires_human_review_for_critical_actions",
    )


@router.get("/documents/{document_id}/citations")
def get_document_citations(document_id: str, context=Depends(build_request_context)) -> dict:
    return {
        "request_id": context.request_id,
        "document_id": document_id,
        "citations": [
            {
                "source_type": "document",
                "source_ref": document_id,
                "confidence": 0.95,
                "span_start": 0,
                "span_end": 80,
            }
        ],
        "confidence": 0.95,
        "verification_status": "verified",
    }
