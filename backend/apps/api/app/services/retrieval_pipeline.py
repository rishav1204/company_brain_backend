from app.services.graph_service import query_related_entities
from app.services.repositories import documents_repo, memory_repo
from app.services.retrieval_service import retrieve_context


def keyword_score(query: str, text: str) -> float:
    query_terms = {term for term in query.lower().split() if term}
    if not query_terms:
        return 0.0
    text_terms = set(text.lower().split())
    overlap = query_terms.intersection(text_terms)
    return len(overlap) / len(query_terms)


def bm25ish_score(query: str, text: str) -> float:
    terms = [term for term in query.lower().split() if term]
    if not terms:
        return 0.0
    lowered = text.lower()
    return sum(lowered.count(term) for term in terms) / max(len(terms), 1)


def graph_awareness_boost(item: str, graph_context: list[str]) -> float:
    lowered = item.lower()
    if any(token.lower() in lowered for token in ("invoice", "workflow", "approval", "incident")):
        if graph_context:
            return 0.1
    return 0.0


def retrieve_hybrid_context(
    org_id: str,
    query: str,
    subject_ref: str | None = None,
    top_k: int = 5,
    metadata_filter: dict | None = None,
) -> dict:
    metadata_filter = metadata_filter or {}
    required_doc_type = metadata_filter.get("doc_type")
    required_tags = set(metadata_filter.get("tags", []))
    allowed_source_refs = metadata_filter.get("allowed_source_refs", [])
    if not isinstance(allowed_source_refs, list):
        allowed_source_refs = []
    metadata_filtered_docs = [
        doc for doc in documents_repo.list_documents(org_id=org_id, doc_type=required_doc_type)
        if (subject_ref is None or subject_ref in doc.get("id", ""))
        and (not required_tags or required_tags.intersection(set(doc.get("tags", []))))
        and (
            not allowed_source_refs
            or doc.get("permission_ref") in allowed_source_refs
            or not str(doc.get("permission_ref", "")).strip()
        )
    ]
    vector_context, vector_citations = retrieve_context(
        org_id=org_id,
        query=query,
        subject_ref=subject_ref,
        top_k=max(top_k * 3, 10),
        metadata_filter=metadata_filter,
    )
    ann_shortlist = vector_context[: max(top_k * 2, 5)]
    graph_context = query_related_entities(org_id=org_id, subject_ref=subject_ref)
    memory_rows = memory_repo.list_high_relevance(org_id=org_id, min_relevance=0.7)
    memory_context = [f"Memory:{row['subject_ref']} -> {row['payload_jsonb']}" for row in memory_rows]
    lexical_context = [f"Doc:{doc['id']} -> {doc.get('citation', '')}" for doc in metadata_filtered_docs]

    source_trust = {"erp": 0.2, "bank": 0.3, "crm": 0.1, "docs": 0.15, "ticketing": 0.1}
    def trust_boost(item: str) -> float:
        lowered = item.lower()
        boost = 0.0
        for key, value in source_trust.items():
            if key in lowered:
                boost += value
        return boost

    merged = ann_shortlist + graph_context + memory_context + lexical_context
    ranked = sorted(
        merged,
        key=lambda item: keyword_score(query, item)
        + (0.15 * bm25ish_score(query, item))
        + graph_awareness_boost(item, graph_context)
        + trust_boost(item),
        reverse=True,
    )
    return {
        "context": ranked[:top_k],
        "citations": vector_citations,
        "graph_trace": graph_context,
        "debug": {
            "metadata_prefilter_count": len(metadata_filtered_docs),
            "ann_shortlist_count": len(ann_shortlist),
            "lexical_candidates_count": len(lexical_context),
        },
    }
