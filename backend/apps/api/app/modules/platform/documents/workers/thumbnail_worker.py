from __future__ import annotations


def process_thumbnail_job(org_id: str, *, document_id: str) -> dict:
    return {"status": "completed", "org_id": org_id, "document_id": document_id, "thumbnail": "not_implemented"}
