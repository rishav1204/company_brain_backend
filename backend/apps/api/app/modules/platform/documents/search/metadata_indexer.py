from __future__ import annotations


def build_metadata_index(document: dict) -> dict:
    return {
        "document_type": document.get("document_type"),
        "file_name": document.get("file_name"),
        "mime_type": document.get("mime_type"),
    }
