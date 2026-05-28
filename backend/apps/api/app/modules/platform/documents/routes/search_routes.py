from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.platform.documents.repositories.extraction_repository import extraction_repository
from app.services.llm_provider import llm_provider

router = APIRouter(tags=["documents-search"])


@router.get("/documents/search/semantic")
def semantic_search(
    context=Depends(build_request_context),
    q: str = Query(..., min_length=2, max_length=1000),
    limit: int = Query(default=20, ge=1, le=50),
    document_type: str | None = Query(default=None),
) -> dict:
    if not llm_provider.is_ready():
        return {"request_id": context.request_id, "items": [], "detail": "Embedding provider not ready"}
    query_embedding = llm_provider.generate_embedding(org_id=context.org_id, text=q)
    items = extraction_repository.search_embeddings(
        context.org_id,
        query_embedding=query_embedding,
        top_k=limit,
        document_type=document_type,
    )
    return {"request_id": context.request_id, "items": items}


@router.get("/documents/search/hybrid")
def hybrid_search(
    context=Depends(build_request_context),
    q: str = Query(..., min_length=2, max_length=1000),
    keyword: str | None = Query(default=None, max_length=200),
    document_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
) -> dict:
    """
    Hybrid search:
    - vector similarity over chunked embeddings (page/section)
    - optional keyword constraint (tsquery) on chunk content
    - optional document_type filter
    """
    if not llm_provider.is_ready():
        return {"request_id": context.request_id, "items": [], "detail": "Embedding provider not ready"}
    query_embedding = llm_provider.generate_embedding(org_id=context.org_id, text=q)
    items = extraction_repository.search_chunk_embeddings(
        context.org_id,
        query_embedding=query_embedding,
        top_k=limit,
        document_type=document_type,
        keyword=keyword,
    )
    return {"request_id": context.request_id, "items": items}

