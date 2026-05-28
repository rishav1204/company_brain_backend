from app.services.llm_provider import llm_provider
from app.services.processing_service import chunk_text, extract_metadata
from app.services.repositories import documents_repo, sources_repo


def ingest_document_for_embedding(
    org_id: str,
    source_id: str,
    title: str,
    content: str,
    doc_type: str = "ops_note",
    permission_ref: str | None = None,
) -> dict:
    if not llm_provider.is_ready():
        return {"status": "skipped", "detail": "LLM embedding provider not ready"}
    source_ref = sources_repo.get_source_ref(org_id=org_id, source_id=source_id)
    document = documents_repo.create_document(
        org_id=org_id,
        source_id=source_id,
        external_id=None,
        title=title,
        doc_type=doc_type,
        permission_ref=permission_ref or source_ref,
    )
    chunks = chunk_text(content)
    inserted = 0
    for index, chunk in enumerate(chunks):
        cleaned = chunk.strip()
        if not cleaned:
            continue
        embedding = llm_provider.generate_embedding(org_id=org_id, text=cleaned)
        metadata = extract_metadata(cleaned)
        metadata["source_ref"] = source_ref or ""
        documents_repo.create_chunk(
            org_id=org_id,
            document_id=document["id"],
            chunk_index=index,
            content=cleaned,
            metadata_jsonb=metadata,
            token_count=max(1, len(cleaned.split())),
            embedding=embedding,
        )
        inserted += 1
    result = {
        "status": "completed",
        "document_id": document["id"],
        "chunks_written": inserted,
    }
    try:
        from app.modules.platform.events.events.ai_events import emit_ocr_requested

        emit_ocr_requested(
            org_id,
            document_id=document["id"],
            source="embedding_ingest",
            idempotency_key=f"ocr:{document['id']}",
        )
        result["ocr_event"] = "queued"
    except Exception:
        result["ocr_event"] = "skipped"
    return result
