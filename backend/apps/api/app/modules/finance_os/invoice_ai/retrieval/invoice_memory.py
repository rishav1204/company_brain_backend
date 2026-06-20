from __future__ import annotations

from app.services.retrieval_service import retrieve_context


def retrieve_past_extractions(org_id: str, *, vendor_gstin: str | None, vendor_name: str, top_k: int = 5) -> list[dict]:
    key = vendor_gstin or vendor_name
    contexts, citations = retrieve_context(
        org_id,
        query=f"past invoice extraction vendor {key}",
        metadata_filter={"doc_type": "invoice"},
        top_k=top_k,
    )
    return [
        {"content": ctx, "score": cite.confidence, "vendor_key": key}
        for ctx, cite in zip(contexts, citations)
    ]
