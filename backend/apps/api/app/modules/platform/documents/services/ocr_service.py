from __future__ import annotations

from app.modules.platform.documents.providers.ocr_provider import ocr_provider
from app.modules.platform.documents.repositories.document_repository import document_repository
from app.modules.platform.documents.repositories.extraction_repository import extraction_repository
from app.modules.platform.documents.search.embedding_indexer import make_embedding
from app.modules.platform.documents.services.extraction_service import extraction_service


class OCRService:
    def process_document(self, org_id: str, *, document_id: str, extraction_type: str = "invoice_ocr") -> dict:
        doc = document_repository.get_document(org_id, document_id)
        if not doc:
            raise ValueError("Document not found")
        ocr_result = ocr_provider.extract_text(
            storage_path=str(doc.get("storage_path", "")),
            mime_type=str(doc.get("mime_type", "")),
        )
        ocr_text = str(ocr_result.get("text", "") or "")
        extraction = extraction_service.extract(
            org_id,
            document_id=document_id,
            extraction_type=extraction_type,
            text=ocr_text,
        )
        # Semantic embedding for search/retrieval.
        if ocr_text.strip():
            try:
                # Whole-document embedding (back-compat)
                embedding = make_embedding(ocr_text[:8000])
                extraction_repository.add_embedding(
                    org_id,
                    document_id=document_id,
                    embedding=embedding,
                    metadata={
                        "source": "ocr",
                        "extraction_type": extraction_type,
                        "mime_type": doc.get("mime_type"),
                        "document_type": doc.get("document_type"),
                    },
                )
            except Exception:
                pass

            # Chunked embeddings: prefer page-level outputs when available.
            try:
                page_outputs = ocr_result.get("page_outputs") or []
                if isinstance(page_outputs, list) and page_outputs:
                    for idx, p in enumerate(page_outputs[:200]):
                        text = str((p or {}).get("text") or "").strip()
                        if not text:
                            continue
                        emb = make_embedding(text[:8000])
                        extraction_repository.add_chunk_embedding(
                            org_id,
                            document_id=document_id,
                            content=text,
                            embedding=emb,
                            page_number=int((p or {}).get("page_number") or (idx + 1)),
                            chunk_index=0,
                            metadata={"source": "ocr_page", "extraction_type": extraction_type},
                        )
                else:
                    # Fallback: split into rough chunks.
                    words = ocr_text.split()
                    chunk_words = 350
                    ci = 0
                    for start in range(0, len(words), chunk_words):
                        chunk = " ".join(words[start : start + chunk_words]).strip()
                        if not chunk:
                            continue
                        emb = make_embedding(chunk[:8000])
                        extraction_repository.add_chunk_embedding(
                            org_id,
                            document_id=document_id,
                            content=chunk,
                            embedding=emb,
                            page_number=None,
                            chunk_index=ci,
                            metadata={"source": "ocr_chunk", "extraction_type": extraction_type},
                        )
                        ci += 1
            except Exception:
                pass
        return {"ocr": ocr_result, "extraction": extraction}


ocr_service = OCRService()
