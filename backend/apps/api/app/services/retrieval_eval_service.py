from app.services.retrieval_pipeline import retrieve_hybrid_context


def evaluate_retrieval(org_id: str, query: str, relevant_markers: list[str], top_k: int = 5) -> dict:
    result = retrieve_hybrid_context(org_id=org_id, query=query, subject_ref=None, top_k=top_k)
    context = result["context"]
    if not context:
        return {
            "precision_at_k": 0.0,
            "recall_at_k": 0.0,
            "ndcg": 0.0,
            "release_gate_passed": False,
        }
    hits = 0
    citation_hits = 0
    for item in context:
        if any(marker.lower() in item.lower() for marker in relevant_markers):
            hits += 1
        if "doc:" in item.lower() or "memory:" in item.lower():
            citation_hits += 1
    precision = hits / max(len(context), 1)
    recall = hits / max(len(relevant_markers), 1)
    ndcg = precision
    citation_precision = citation_hits / max(len(context), 1)
    hallucination_rate = max(0.0, 1.0 - citation_precision)
    groundedness = min(1.0, (precision + citation_precision) / 2.0)
    release_gate_passed = (
        precision >= 0.95
        and recall >= 0.9
        and ndcg >= 0.9
        and citation_precision >= 0.95
        and groundedness >= 0.9
        and hallucination_rate <= 0.03
    )
    return {
        "precision_at_k": round(precision, 4),
        "recall_at_k": round(recall, 4),
        "ndcg": round(ndcg, 4),
        "citation_precision": round(citation_precision, 4),
        "groundedness": round(groundedness, 4),
        "hallucination_rate": round(hallucination_rate, 4),
        "release_gate_passed": release_gate_passed,
    }
