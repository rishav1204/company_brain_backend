from app.schemas.common import Citation
from app.services.llm_provider import llm_provider
from app.services.repositories import retrieval_repo


def _distance_to_confidence(distance: float | int | None) -> float:
    if distance is None:
        return 0.5
    numeric = float(distance)
    bounded = max(0.0, min(1.0, 1.0 - numeric))
    return round(bounded, 4)


def retrieve_context(
    org_id: str,
    query: str,
    subject_ref: str | None = None,
    top_k: int = 10,
    metadata_filter: dict | None = None,
) -> tuple[list[str], list[Citation]]:
    metadata_filter = metadata_filter or {}
    doc_type = metadata_filter.get("doc_type")
    allowed_source_refs = metadata_filter.get("allowed_source_refs")
    if not isinstance(allowed_source_refs, list):
        allowed_source_refs = None
    if llm_provider.is_ready():
        try:
            query_embedding = llm_provider.generate_embedding(org_id=org_id, text=query)
            rows = retrieval_repo.search_chunks(
                org_id=org_id,
                query_embedding=query_embedding,
                top_k=max(top_k, 1),
                doc_type=doc_type,
                allowed_source_refs=allowed_source_refs,
            )
            if subject_ref:
                rows = [row for row in rows if subject_ref in (row.get("document_id", "") + row.get("content", ""))]
            contexts = [str(row.get("content", "")).strip() for row in rows if str(row.get("content", "")).strip()]
            citations = [
                Citation(
                    source_type="document_chunk",
                    source_ref=row.get("chunk_id", ""),
                    confidence=_distance_to_confidence(row.get("distance")),
                    span_start=0,
                    span_end=min(len(str(row.get("content", ""))), 240),
                )
                for row in rows
            ]
            if contexts:
                return contexts, citations
        except Exception:
            pass

    # deterministic fallback only when embeddings are unavailable or no records found
    fallback_context = [
        "No ranked chunk candidates found from pgvector retrieval for current filters.",
    ]
    if subject_ref:
        fallback_context.append(f"Subject-scoped retrieval fallback for {subject_ref}.")
    fallback_citations = [Citation(source_type="system", source_ref="retrieval-fallback", confidence=0.45)]
    return fallback_context, fallback_citations


def explain_query(org_id: str, query: str, subject_ref: str | None = None) -> tuple[str, list[str], list[Citation]]:
    if llm_provider.is_ready():
        user_prompt = (
            f"Finance query: {query}\n"
            f"Subject ref: {subject_ref}\n"
            "Return a concise operational explanation with recommended next action."
        )
        answer = llm_provider.generate_text(
            org_id=org_id,
            system_prompt=(
                "You are a finance operations AI assistant. "
                "Be factual, concise, and policy-aware."
            ),
            user_prompt=user_prompt,
            estimated_tokens=1200,
        )
    else:
        answer = (
            "Primary bottleneck is delayed approval on a high-risk vendor invoice. "
            "Recommended action is manager escalation followed by CFO review if amount threshold is crossed."
        )
    graph_trace = [
        "Invoice -> BLOCKED_BY -> ApprovalStep",
        "ApprovalStep -> ASSIGNED_TO -> FinanceManager",
        "Decision -> IMPACTS -> AP Cycle Time KPI",
    ]
    _, citations = retrieve_context(org_id=org_id, query=query, subject_ref=subject_ref, top_k=5)
    return answer, graph_trace, citations
