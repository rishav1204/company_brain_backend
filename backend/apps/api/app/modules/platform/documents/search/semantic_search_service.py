from __future__ import annotations

from app.modules.platform.documents.services.document_search_service import document_search_service


def search_documents(org_id: str, *, query: str, limit: int = 20) -> list[dict]:
    return document_search_service.search(org_id, query=query, limit=limit)
