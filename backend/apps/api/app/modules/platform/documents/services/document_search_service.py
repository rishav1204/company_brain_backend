from __future__ import annotations

from app.modules.platform.documents.repositories.document_repository import document_repository


class DocumentSearchService:
    def search(self, org_id: str, *, query: str, limit: int = 20) -> list[dict]:
        query_norm = query.strip().lower()
        docs = document_repository.list_documents(org_id, limit=max(1, min(limit, 200)))
        if not query_norm:
            return docs
        out = []
        for doc in docs:
            hay = " ".join(
                [
                    str(doc.get("file_name", "")),
                    str(doc.get("document_type", "")),
                    str(doc.get("mime_type", "")),
                    str(doc.get("metadata", "")),
                ]
            ).lower()
            if query_norm in hay:
                out.append(doc)
        return out


document_search_service = DocumentSearchService()
